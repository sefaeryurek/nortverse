"""Pipeline runner (runner.py) birim testleri.

_with_retry, _result_to_row, _validate_row, _merge_result_scores.
"""

from __future__ import annotations

import asyncio
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
