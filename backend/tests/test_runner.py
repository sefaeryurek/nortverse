"""Pipeline runner (runner.py) birim testleri.

_with_retry, _result_to_row, _validate_row, _merge_result_scores.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.pipeline.runner import (
    StaleAnalysisWrite,
    _merge_result_scores,
    _result_to_row,
    _validate_row,
    _with_retry,
)
from app.models import MatchAnalysisResult, MatchRawData, Period, PeriodAnalysis


def _period() -> PeriodAnalysis:
    return PeriodAnalysis(
        period=Period.FT,
        scores_1=["1-0"],
        scores_x=[],
        scores_2=[],
        all_ratios={"1-0": 4.0},
    )


def _result(mid: str = "123", home: str = "A", away: str = "B",
            league: str = "TUR D1") -> MatchAnalysisResult:
    return MatchAnalysisResult(
        match_id=mid,
        home_team=home,
        away_team=away,
        league_code=league,
        season="2025/2026",
        n_matches=5,
        threshold=3.5,
        ht=_period(),
        half2=_period(),
        ft=_period(),
    )


def _existing(ft_h=2, ft_a=1, ht_h=None, ht_a=None, h2_h=None, h2_a=None):
    return SimpleNamespace(
        actual_ft_home=ft_h, actual_ft_away=ft_a,
        actual_ht_home=ht_h, actual_ht_away=ht_a,
        actual_h2_home=h2_h, actual_h2_away=h2_a,
    )


# ─── _with_retry ─────────────────────────────────────────────────────────────

class TestWithRetry:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        op = AsyncMock(return_value=42)
        result = await _with_retry(op, "test", attempts=3, base_delay=0.001)
        assert result == 42
        assert op.await_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retries(self):
        op = AsyncMock(side_effect=[RuntimeError("fail"), RuntimeError("fail"), "ok"])
        result = await _with_retry(op, "test", attempts=3, base_delay=0.001)
        assert result == "ok"
        assert op.await_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        op = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError, match="boom"):
            await _with_retry(op, "test", attempts=2, base_delay=0.001)
        assert op.await_count == 2

    @pytest.mark.asyncio
    async def test_value_error_not_retried(self):
        op = AsyncMock(side_effect=ValueError("bad data"))
        with pytest.raises(ValueError, match="bad data"):
            await _with_retry(op, "test", attempts=3, base_delay=0.001)
        assert op.await_count == 1

    @pytest.mark.asyncio
    async def test_integrity_error_not_retried(self):
        from sqlalchemy.exc import IntegrityError
        op = AsyncMock(side_effect=IntegrityError("INSERT", {}, Exception("dup")))
        with pytest.raises(IntegrityError):
            await _with_retry(op, "test", attempts=3, base_delay=0.001)
        assert op.await_count == 1


# ─── _result_to_row ─────────────────────────────────────────────────────────

class TestResultToRow:
    def test_basic_fields(self):
        r = _result()
        row = _result_to_row(r)
        assert row["match_id"] == "123"
        assert row["home_team"] == "A"
        assert row["away_team"] == "B"
        assert row["season"] == "2025/2026"
        assert row["ft_scores_1"] == ["1-0"]

    def test_canonical_league_code(self):
        r = _result(league="ENG PR")
        row = _result_to_row(r)
        assert row["league_code"] == "English Premier League"
        assert row["league_name"] == "English Premier League"

    def test_raw_kickoff_included(self):
        r = _result()
        raw = MatchRawData(
            match_id="123", home_team="A", away_team="B", league_code="TUR D1",
            kickoff_time=datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc),
        )
        row = _result_to_row(r, raw)
        assert row["kickoff_time"] == raw.kickoff_time

    def test_no_raw_kickoff_none(self):
        row = _result_to_row(_result())
        assert row["kickoff_time"] is None

    def test_patterns_merged(self):
        patterns = {"pattern_ft_b": {"key": "val"}, "pattern_ft_c": None}
        row = _result_to_row(_result(), patterns=patterns)
        assert row["pattern_ft_b"] == {"key": "val"}
        assert row["pattern_ft_c"] is None

    def test_trends_computed_from_raw(self, monkeypatch):
        raw = MatchRawData(
            match_id="123", home_team="A", away_team="B", league_code="TUR D1",
        )
        monkeypatch.setattr(
            "app.pipeline.runner.compute_trends",
            lambda r: SimpleNamespace(model_dump=lambda: {"home_form": {}}),
        )
        row = _result_to_row(_result(), raw)
        assert row["trends"] == {"home_form": {}}

    def test_trends_error_returns_none(self, monkeypatch):
        raw = MatchRawData(
            match_id="123", home_team="A", away_team="B", league_code="TUR D1",
        )
        monkeypatch.setattr(
            "app.pipeline.runner.compute_trends",
            lambda r: (_ for _ in ()).throw(RuntimeError("fail")),
        )
        row = _result_to_row(_result(), raw)
        assert row["trends"] is None


# ─── _validate_row ───────────────────────────────────────────────────────────

class TestValidateRow:
    def test_valid_row(self):
        ok, reason = _validate_row({
            "home_team": "Fenerbahce",
            "away_team": "Galatasaray",
            "league_code": "Turkish Super Lig",
        })
        assert ok
        assert reason is None

    def test_empty_home_team(self):
        ok, reason = _validate_row({
            "home_team": "",
            "away_team": "B",
            "league_code": "TUR D1",
        })
        assert not ok
        assert "home_team" in reason

    def test_question_mark_away(self):
        ok, reason = _validate_row({
            "home_team": "A",
            "away_team": "?",
            "league_code": "TUR D1",
        })
        assert not ok
        assert "away_team" in reason

    def test_empty_league_code(self):
        ok, reason = _validate_row({
            "home_team": "A",
            "away_team": "B",
            "league_code": "",
        })
        assert not ok
        assert "league_code" in reason

    def test_cup_league_rejected(self):
        ok, reason = _validate_row({
            "home_team": "A",
            "away_team": "B",
            "league_code": "UEFA Champions League",
        })
        assert not ok
        assert "kupa" in reason.lower() or "lig" in reason.lower()

    def test_negative_score(self):
        ok, reason = _validate_row({
            "home_team": "A",
            "away_team": "B",
            "league_code": "Turkish Super Lig",
            "actual_ft_home": -1,
        })
        assert not ok
        assert "aralık" in reason

    def test_absurd_score(self):
        ok, reason = _validate_row({
            "home_team": "A",
            "away_team": "B",
            "league_code": "Turkish Super Lig",
            "actual_ft_away": 31,
        })
        assert not ok

    def test_none_score_accepted(self):
        ok, _ = _validate_row({
            "home_team": "A",
            "away_team": "B",
            "league_code": "Turkish Super Lig",
            "actual_ft_home": None,
        })
        assert ok


# ─── _merge_result_scores ───────────────────────────────────────────────────

class TestMergeResultScores:
    def test_full_scores(self):
        raw = MatchRawData(
            match_id="1", home_team="A", away_team="B", league_code="X",
            actual_ft_home=3, actual_ft_away=1,
            actual_ht_home=1, actual_ht_away=0,
            actual_h2_home=2, actual_h2_away=1,
        )
        result = _merge_result_scores(raw, _existing())
        assert result["actual_ft_home"] == 3
        assert result["actual_ht_home"] == 1
        assert result["actual_h2_home"] == 2

    def test_ht_only_derives_h2(self):
        raw = MatchRawData(
            match_id="1", home_team="A", away_team="B", league_code="X",
            actual_ft_home=3, actual_ft_away=1,
            actual_ht_home=1, actual_ht_away=0,
        )
        result = _merge_result_scores(raw, _existing())
        assert result["actual_h2_home"] == 2
        assert result["actual_h2_away"] == 1

    def test_h2_only_derives_ht(self):
        raw = MatchRawData(
            match_id="1", home_team="A", away_team="B", league_code="X",
            actual_ft_home=3, actual_ft_away=1,
            actual_h2_home=2, actual_h2_away=1,
        )
        result = _merge_result_scores(raw, _existing())
        assert result["actual_ht_home"] == 1
        assert result["actual_ht_away"] == 0

    def test_preserves_existing_ht_when_ft_unchanged(self):
        raw = MatchRawData(
            match_id="1", home_team="A", away_team="B", league_code="X",
            actual_ft_home=2, actual_ft_away=1,
        )
        existing = _existing(ft_h=2, ft_a=1, ht_h=1, ht_a=0)
        result = _merge_result_scores(raw, existing)
        assert result["actual_ht_home"] == 1
        assert result["actual_ht_away"] == 0
        assert result["actual_h2_home"] == 1
        assert result["actual_h2_away"] == 1

    def test_invalid_ft_raises(self):
        raw = MatchRawData(
            match_id="1", home_team="A", away_team="B", league_code="X",
            actual_ft_home=-1, actual_ft_away=0,
        )
        with pytest.raises(ValueError, match="Invalid final score"):
            _merge_result_scores(raw, _existing())

    def test_inconsistent_halves_raises(self):
        raw = MatchRawData(
            match_id="1", home_team="A", away_team="B", league_code="X",
            actual_ft_home=3, actual_ft_away=2,
            actual_ht_home=1, actual_ht_away=0,
            actual_h2_home=1, actual_h2_away=1,  # 1+1=2 != 3, 0+1=1 != 2
        )
        with pytest.raises(ValueError, match="Half scores do not match"):
            _merge_result_scores(raw, _existing())


# ─── StaleAnalysisWrite ─────────────────────────────────────────────────────

class TestStaleAnalysisWrite:
    def test_is_value_error(self):
        exc = StaleAnalysisWrite("old data")
        assert isinstance(exc, ValueError)

    def test_message(self):
        exc = StaleAnalysisWrite("stale 123")
        assert "stale 123" in str(exc)


@pytest.mark.asyncio
async def test_sync_kickoffs_updates_only_changed_unfinished_matches():
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, MagicMock
    from app.pipeline import runner

    old = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
    new = datetime(2026, 10, 18, 10, 30, tzinfo=timezone.utc)
    session = AsyncMock()
    session.execute.side_effect = [MagicMock(all=lambda: [("1", old), ("2", new)]), MagicMock()]
    items = [{"match_id": "1", "kickoff_time": new.isoformat()},
             {"match_id": "2", "kickoff_time": new.isoformat()},
             {"match_id": "3", "kickoff_time": None}]
    assert await runner.sync_kickoffs(session, items) == 1
    update = session.execute.await_args_list[1].args[0]
    assert update.table.name == "matches"
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_carried_cache_items_do_not_set_kickoff():
    """Kaynak listesinden düşmüş (ertelenmiş olabilecek) maçın eski saati geri yazılmaz."""
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock
    from app.pipeline import runner

    stale = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
    session = AsyncMock()
    items = [{"match_id": "1", "kickoff_time": stale.isoformat(), "carried": True}]
    assert await runner.sync_kickoffs(session, items) == 0
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_cache_sync_prefers_most_recently_fetched_day(monkeypatch):
    """Maç D gününden D+1'e ertelendi; D'nin eski listesi ile D+1'in yeni listesi çakışırsa yeni kazanır."""
    from contextlib import asynccontextmanager
    from datetime import date, datetime, timezone
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.pipeline import runner

    old_time = datetime(2026, 10, 18, 17, 0, tzinfo=timezone.utc)
    new_time = datetime(2026, 10, 19, 17, 0, tzinfo=timezone.utc)
    caches = {
        "2026-10-18": SimpleNamespace(cached_at=datetime(2026, 10, 17, 8, tzinfo=timezone.utc),
                                      matches_json=[{"match_id": "9", "kickoff_time": old_time.isoformat()}]),
        "2026-10-19": SimpleNamespace(cached_at=datetime(2026, 10, 18, 9, tzinfo=timezone.utc),
                                      matches_json=[{"match_id": "9", "kickoff_time": new_time.isoformat()}]),
    }
    session = AsyncMock()
    session.get.side_effect = lambda _model, key: caches.get(key)
    captured = {}

    async def fake_sync(_session, items):
        captured["items"] = items
        return 1

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(runner, "get_session", fake_session)
    monkeypatch.setattr(runner, "sync_kickoffs", fake_sync)
    # Gün sırası ters verilse de sonuç aynı: belirleyici olan çekilme zamanı
    assert await runner.sync_kickoffs_from_cache([date(2026, 10, 19), date(2026, 10, 18)]) == 1
    assert captured["items"] == [{"match_id": "9", "kickoff_time": new_time.isoformat()}]


@pytest.mark.asyncio
async def test_retained_cache_items_are_marked_carried(monkeypatch):
    from contextlib import asynccontextmanager
    from datetime import date, datetime, timezone
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.pipeline import runner

    kickoff = datetime(2026, 10, 19, 17, tzinfo=timezone.utc)
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(matches_json=[{"match_id": "5", "kickoff_time": kickoff.isoformat()}])

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(runner, "get_session", fake_session)
    monkeypatch.setattr(runner, "sync_kickoffs_from_cache", AsyncMock(return_value=0))
    assert await runner.save_fixture_cache(date(2026, 10, 19), []) == 1
    assert session.merge.await_args.args[0].matches_json[0]["carried"] is True


def test_pipeline_exit_code_rule():
    """Tek tük zaman aşımı uyarı vermez; hiç kayıt yoksa ya da hatalar çoksa görev hata döner."""
    from app.cli.pipeline_cmds import pipeline_failed
    assert not pipeline_failed({"analyzed": 78, "errors": 2, "skipped": 68})
    assert not pipeline_failed({"analyzed": 0, "errors": 0, "skipped": 10})
    assert pipeline_failed({"analyzed": 0, "errors": 3})
    assert pipeline_failed({"analyzed": 20, "errors": 9})
    assert not pipeline_failed({"analyzed": 20, "errors": 5})


def test_shrunk_fixture_list_threshold():
    """Sprint 94 F11: yeni liste öncekinin yarısından küçükse uyarı (küçük günlerde gürültü yok)."""
    from app.pipeline.runner import shrunk_fixture_list

    assert shrunk_fixture_list(300, 7) is True
    assert shrunk_fixture_list(300, 160) is False
    assert shrunk_fixture_list(10, 2) is False


def test_prune_old_skips_deletes_before_retention(monkeypatch):
    import asyncio
    from contextlib import asynccontextmanager
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from app.analysis import skip_cache

    seen = []

    class _S:
        async def execute(self, stmt):
            seen.append(stmt)
            return SimpleNamespace(rowcount=4)

    @asynccontextmanager
    async def fake_session():
        yield _S()

    monkeypatch.setattr(skip_cache, "get_session", fake_session)
    now = datetime(2026, 10, 29, tzinfo=timezone.utc)
    assert asyncio.run(skip_cache.prune_old_skips(now)) == 4
    params = seen[0].compile().params
    assert list(params.values()) == [now - skip_cache.SKIP_RETENTION]
