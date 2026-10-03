"""Canlı İY Eşleşme (routes_live_ht.py) birim testleri."""

from __future__ import annotations

import pytest

from app.api.routes_live_ht import (
    LiveHTStats,
    _is_ht_window,
    _cleanup_observed,
    _ht_observed,
    _ht_observed_day,
)


class TestIsHTWindow:
    def test_ht_string(self):
        assert _is_ht_window("HT") is True

    def test_minute_46(self):
        assert _is_ht_window("46") is True

    def test_minute_55(self):
        assert _is_ht_window("55") is True

    def test_minute_60(self):
        assert _is_ht_window("60") is True

    def test_minute_61(self):
        assert _is_ht_window("61") is False

    def test_minute_45_plus(self):
        assert _is_ht_window("45+2") is False

    def test_minute_46_plus(self):
        assert _is_ht_window("46+1") is True

    def test_first_half(self):
        assert _is_ht_window("30") is False

    def test_none(self):
        assert _is_ht_window(None) is False

    def test_empty(self):
        assert _is_ht_window("") is False

    def test_non_numeric(self):
        assert _is_ht_window("abc") is False


class TestLiveHTStatsModel:
    def test_default_values(self):
        stats = LiveHTStats(ht_score="1-0", archive_count=0)
        assert stats.ft_result_1_pct == 0.0
        assert stats.ft_result_x_pct == 0.0
        assert stats.ft_result_2_pct == 0.0
        assert stats.ft_ust_25_pct == 0.0
        assert stats.ft_kg_var_pct == 0.0
        assert stats.h2_result_1_pct == 0.0
        assert stats.top_ft_scores == []

    def test_with_values(self):
        stats = LiveHTStats(
            ht_score="1-0",
            archive_count=100,
            ft_result_1_pct=68.2,
            ft_result_x_pct=18.1,
            ft_result_2_pct=13.7,
            ft_ust_25_pct=55.3,
            ft_kg_var_pct=42.1,
            h2_result_1_pct=42.5,
            h2_result_x_pct=30.0,
            h2_result_2_pct=27.5,
            top_ft_scores=[{"score": "2-0", "count": 20, "pct": 20.0}],
        )
        assert stats.archive_count == 100
        assert stats.ft_result_1_pct == 68.2
        assert len(stats.top_ft_scores) == 1


class TestCleanupObserved:
    def test_clears_on_new_day(self):
        import app.api.routes_live_ht as mod
        mod._ht_observed["test"] = (1, 0)
        mod._ht_observed_day = "2020-01-01"
        _cleanup_observed()
        assert "test" not in mod._ht_observed

    def test_keeps_on_same_day(self):
        import app.api.routes_live_ht as mod
        from datetime import datetime, timedelta, timezone
        today = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d")
        mod._ht_observed["test"] = (2, 1)
        mod._ht_observed_day = today
        _cleanup_observed()
        assert "test" in mod._ht_observed


class TestStatsEndpoint:
    @pytest.mark.asyncio
    async def test_invalid_score_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            from app.api.routes_live_ht import get_live_ht_stats
            await get_live_ht_stats(-1, 0)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_high_score_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            from app.api.routes_live_ht import get_live_ht_stats
            await get_live_ht_stats(16, 0)
        assert exc_info.value.status_code == 400
