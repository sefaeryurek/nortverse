"""update-scores dayanıklılığı (Sprint 94 B1): bir günün hatası diğer günleri, defteri ve kuponları durdurmaz."""

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import typer

import app.analysis.coupons as coupons
import app.analysis.ledger as ledger
import app.db.connection as connection
import app.pipeline as pipeline
import app.pipeline.runner as runner
from app.cli.pipeline_cmds import update_scores_cmd
from app.db.models import FixtureCache

TODAY = date(2026, 10, 27)
OK = {"updated": 1, "unchanged": 0, "not_finished": 0, "skipped": 0, "errors": 0, "source_empty": False}


def _patch(monkeypatch, update, pending_days):
    calls: dict[str, list] = {"days": [], "resolve": [], "settle": []}

    async def fake_update(target_date=None):
        calls["days"].append(target_date)
        return await update(target_date)

    async def fake_resolve():
        calls["resolve"].append(1)
        return {"resolved": 0, "void": 0, "unresolvable": 0}

    async def fake_settle(_session):
        calls["settle"].append(1)
        return 0

    @asynccontextmanager
    async def fake_session():
        yield object()

    monkeypatch.setattr(pipeline, "update_results", fake_update)
    monkeypatch.setattr(runner, "pending_result_days", AsyncMock(return_value=pending_days))
    monkeypatch.setattr(runner, "default_result_day", lambda now=None: TODAY)
    monkeypatch.setattr(ledger, "resolve_pending", fake_resolve)
    monkeypatch.setattr(coupons, "settle_pending", fake_settle)
    monkeypatch.setattr(connection, "get_session", fake_session)
    return calls


def test_update_scores_continues_after_one_pending_day_fails(monkeypatch):
    async def update(day):
        if day == date(2026, 10, 25):
            raise TimeoutError("kaynak yanıt vermedi")
        return OK

    calls = _patch(monkeypatch, update, [date(2026, 10, 25), date(2026, 10, 26)])
    with pytest.raises(typer.Exit) as exc:
        update_scores_cmd(target_date=None, pending_days=3, verbose=False)
    assert exc.value.exit_code == 2
    assert calls["days"] == [TODAY, date(2026, 10, 25), date(2026, 10, 26)]


def test_update_scores_still_resolves_ledger_and_coupons_on_day_failure(monkeypatch):
    async def update(_day):
        raise TimeoutError("kaynak yanıt vermedi")

    calls = _patch(monkeypatch, update, [])
    with pytest.raises(typer.Exit):
        update_scores_cmd(target_date=None, pending_days=0, verbose=False)
    assert calls["resolve"] == [1] and calls["settle"] == [1]


def test_pending_days_skips_default_target_day(monkeypatch):
    async def update(_day):
        return OK

    calls = _patch(monkeypatch, update, [date(2026, 10, 26), TODAY])
    update_scores_cmd(target_date=None, pending_days=3, verbose=False)  # hata yok → Exit yok
    assert calls["days"] == [TODAY, date(2026, 10, 26)]  # bugün iki kez işlenmez


def test_source_empty_day_fails_the_command(monkeypatch):
    async def update(_day):
        return {**OK, "updated": 0, "skipped": 5, "errors": 1, "source_empty": True}

    _patch(monkeypatch, update, [])
    with pytest.raises(typer.Exit) as exc:
        update_scores_cmd(target_date=None, pending_days=0, verbose=False)
    assert exc.value.exit_code == 2


def test_default_result_day_uses_previous_day_before_4am():
    assert runner.default_result_day(datetime(2026, 10, 27, 18, 0, tzinfo=timezone.utc)) == date(2026, 10, 27)  # 21:00
    assert runner.default_result_day(datetime(2026, 10, 27, 22, 30, tzinfo=timezone.utc)) == date(2026, 10, 27)  # 01:30
    assert runner.default_result_day(datetime(2026, 10, 28, 2, 0, tzinfo=timezone.utc)) == date(2026, 10, 28)  # 05:00


@pytest.mark.asyncio
async def test_empty_source_page_counts_as_error(monkeypatch):
    session = AsyncMock()
    session.get.return_value = FixtureCache(
        date="2026-10-27", cached_at=datetime.now(timezone.utc),
        matches_json=[{"match_id": "123", "home_team": "A", "away_team": "B", "league_code": "ENG PR"}],
    )
    selected = MagicMock()
    selected.scalars.return_value.all.return_value = []
    session.execute.return_value = selected

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(runner, "get_session", get_session)
    monkeypatch.setattr(runner, "fetch_fixture_scores", AsyncMock(return_value={}))
    stats = await runner.update_results(TODAY)
    assert stats["source_empty"] is True and stats["errors"] == 1 and stats["updated"] == 0


@pytest.mark.asyncio
async def test_unchanged_fixture_score_is_not_counted_as_updated(monkeypatch):
    session = AsyncMock()
    session.get.return_value = FixtureCache(
        date="2026-10-27", cached_at=datetime.now(timezone.utc),
        matches_json=[{"match_id": "123", "home_team": "A", "away_team": "B", "league_code": "ENG PR",
                       "score_status": "finished", "score_home": 2, "score_away": 1}],
    )
    selected = MagicMock()
    selected.scalars.return_value.all.return_value = []
    session.execute.return_value = selected

    @asynccontextmanager
    async def get_session():
        yield session

    from app.scraper.fixture_scores import FixtureScore

    monkeypatch.setattr(runner, "get_session", get_session)
    monkeypatch.setattr(runner, "fetch_fixture_scores",
                        AsyncMock(return_value={"123": FixtureScore("123", "finished", 2, 1, 1, 0)}))
    stats = await runner.update_results(TODAY)
    assert stats["updated"] == 0 and stats["unchanged"] == 1
