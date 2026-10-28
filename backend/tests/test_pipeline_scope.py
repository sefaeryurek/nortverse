"""Pipeline kapsamı ve sessiz sıfır korumaları (Sprint 94 F1, F2, F5)."""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.cli.pipeline_cmds import pipeline_failed
from app.models import FixtureMatch, MatchRawData, SkipReason
from app.pipeline import runner

SOON = datetime.now(timezone.utc) + timedelta(hours=5)


def _fx(mid, league, kickoff=SOON):
    return FixtureMatch(match_id=mid, home_team=f"H{mid}", away_team=f"A{mid}", league_code=league,
                        league_name=league, kickoff_time=kickoff)


def _patch(monkeypatch, fixtures, *, reason=SkipReason.H2H_INSUFFICIENT):
    @asynccontextmanager
    async def fake_browser():
        yield object()

    monkeypatch.setattr(runner, "browser_context", fake_browser)
    monkeypatch.setattr(runner, "fetch_istanbul_fixture", AsyncMock(return_value=fixtures))
    monkeypatch.setattr(runner, "save_fixture_cache", AsyncMock(return_value=len(fixtures)))
    seen: list[str] = []

    async def detail(mid, ctx=None, expected_league_name=None):
        seen.append(mid)
        return MatchRawData(match_id=mid, home_team="H", away_team="A", league_code=expected_league_name or "")

    monkeypatch.setattr(runner, "fetch_match_detail", detail)
    monkeypatch.setattr(runner, "check_match_filters", lambda _raw: SimpleNamespace(passed=False, reason=reason))
    monkeypatch.setattr(runner, "save_skip", AsyncMock())
    return seen


@pytest.mark.asyncio
async def test_tracked_scope_skips_untracked_leagues_and_orders_by_kickoff(monkeypatch):
    late = _fx("1", "English Premier League", SOON + timedelta(hours=3))
    minor = _fx("2", "Chile Primera B", SOON - timedelta(hours=2))
    early = _fx("3", "Portugal Primeira Liga", SOON)
    seen = _patch(monkeypatch, [late, minor, early])
    await runner.run_pipeline()
    assert seen == ["3", "1"]  # küçük lig hiç işlenmez, en erken takip maçı önce


@pytest.mark.asyncio
async def test_all_scope_processes_tracked_first(monkeypatch):
    minor = _fx("2", "Chile Primera B", SOON - timedelta(hours=2))
    main = _fx("1", "English Premier League", SOON + timedelta(hours=3))
    seen = _patch(monkeypatch, [minor, main])
    await runner.run_pipeline(scope="all")
    assert seen == ["1", "2"]


@pytest.mark.asyncio
async def test_started_tracked_match_is_counted_as_missed(monkeypatch):
    started = _fx("1", "English Premier League", datetime.now(timezone.utc) - timedelta(minutes=5))
    _patch(monkeypatch, [started])
    stats = await runner.run_pipeline()
    assert stats["missed_started"] == 1 and stats["skipped"] == 1


@pytest.mark.asyncio
async def test_empty_source_bulletin_is_retried_then_fails(monkeypatch):
    @asynccontextmanager
    async def fake_browser():
        yield object()

    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(runner, "browser_context", fake_browser)
    monkeypatch.setattr(runner, "fetch_istanbul_fixture", fetch)
    monkeypatch.setattr(runner, "FIXTURE_RETRY_DELAYS", (0, 0))
    save = AsyncMock()
    monkeypatch.setattr(runner, "save_fixture_cache", save)
    stats = await runner.run_pipeline()
    assert fetch.await_count == 3 and stats["source_empty"] is True
    save.assert_not_awaited()  # boş liste iyi önbelleğin üstüne yazılmaz
    assert pipeline_failed(stats)


@pytest.mark.asyncio
async def test_fixture_fetch_error_then_success(monkeypatch):
    @asynccontextmanager
    async def fake_browser():
        yield object()

    fetch = AsyncMock(side_effect=[OSError("getaddrinfo failed"), [_fx("1", "English Premier League")]])
    monkeypatch.setattr(runner, "fetch_istanbul_fixture", fetch)
    monkeypatch.setattr(runner, "FIXTURE_RETRY_DELAYS", (0,))
    fixtures = await runner._fetch_fixture_with_retry(SOON.date(), False, object())
    assert [f.match_id for f in fixtures] == ["1"]


@pytest.mark.asyncio
async def test_h2h_alarm_when_most_main_league_matches_fail_h2h(monkeypatch):
    fixtures = [_fx(str(i), "English Premier League") for i in range(5)]
    _patch(monkeypatch, fixtures)
    stats = await runner.run_pipeline()
    assert stats["h2h_alarm"] is True and pipeline_failed(stats)


@pytest.mark.asyncio
async def test_no_h2h_alarm_for_other_skip_reasons(monkeypatch):
    fixtures = [_fx(str(i), "English Premier League") for i in range(5)]
    _patch(monkeypatch, fixtures, reason=SkipReason.HOME_TEAM_INSUFFICIENT)
    stats = await runner.run_pipeline()
    assert stats["h2h_alarm"] is False and not pipeline_failed(stats)
