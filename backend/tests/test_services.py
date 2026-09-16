"""API iş mantığı (services.py) birim testleri.

cache_put, cache_get, get_or_make_lock, _pat, _trends_parse,
enqueue_bg_analysis, init/shutdown_bg_queue.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.api.schemas import AnalyzeResponse, PeriodOut
from app.api.services import (
    ANALYSIS_CACHE_TTL,
    _CACHE_MAX,
    _analysis_cached_at,
    _pat,
    _trends_parse,
    analysis_cache,
    cache_get,
    cache_put,
    enqueue_bg_analysis,
    get_or_make_lock,
    init_bg_queue,
    shutdown_bg_queue,
    bg_queue,
    _bg_queued,
)


def _resp(mid: str = "123") -> AnalyzeResponse:
    return AnalyzeResponse(
        match_id=mid,
        home_team="A",
        away_team="B",
        league_code="X",
        season="2025/2026",
        ht=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
        half2=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
        ft=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
    )


@pytest.fixture(autouse=True)
def _clean_cache():
    """Her test öncesi cache'i temizle."""
    analysis_cache.clear()
    _analysis_cached_at.clear()
    yield
    analysis_cache.clear()
    _analysis_cached_at.clear()


# ─── cache_put / cache_get ──────────────────────────────────────────────────

class TestCachePut:
    def test_put_and_get(self):
        r = _resp("m1")
        cache_put("m1", r)
        assert cache_get("m1") is r

    def test_cache_miss(self):
        assert cache_get("nonexistent") is None

    def test_lru_eviction(self):
        for i in range(_CACHE_MAX + 5):
            cache_put(f"m{i}", _resp(f"m{i}"))
        assert len(analysis_cache) == _CACHE_MAX
        assert cache_get("m0") is None
        assert cache_get("m1") is None
        assert cache_get(f"m{_CACHE_MAX + 4}") is not None

    def test_move_to_end_on_put(self):
        cache_put("m1", _resp("m1"))
        cache_put("m2", _resp("m2"))
        cache_put("m1", _resp("m1"))
        keys = list(analysis_cache.keys())
        assert keys[-1] == "m1"

    def test_move_to_end_on_get(self):
        cache_put("m1", _resp("m1"))
        cache_put("m2", _resp("m2"))
        cache_get("m1")
        keys = list(analysis_cache.keys())
        assert keys[-1] == "m1"


class TestCacheGet:
    def test_ttl_expired(self):
        cache_put("m1", _resp("m1"))
        _analysis_cached_at["m1"] = time.monotonic() - ANALYSIS_CACHE_TTL - 1
        assert cache_get("m1") is None
        assert "m1" not in analysis_cache

    def test_ttl_not_expired(self):
        cache_put("m1", _resp("m1"))
        assert cache_get("m1") is not None

    def test_missing_cached_at_treated_as_expired(self):
        cache_put("m1", _resp("m1"))
        _analysis_cached_at.pop("m1", None)
        result = cache_get("m1")
        assert result is None


# ─── get_or_make_lock ───────────────────────────────────────────────────────

class TestGetOrMakeLock:
    def test_same_id_same_lock(self):
        lock1 = get_or_make_lock("m1")
        lock2 = get_or_make_lock("m1")
        assert lock1 is lock2

    def test_different_id_different_lock(self):
        lock1 = get_or_make_lock("m1")
        lock2 = get_or_make_lock("m2")
        assert lock1 is not lock2

    def test_returns_asyncio_lock(self):
        lock = get_or_make_lock("m1")
        assert isinstance(lock, asyncio.Lock)


# ─── _pat ───────────────────────────────────────────────────────────────────

def _minimal_pattern_blob(match_count: int = 10) -> dict:
    """PatternResult zorunlu alanları sağlayan minimal blob."""
    from app.analysis.pattern_stats import PatternResult
    fields = PatternResult.model_fields
    blob: dict = {}
    for name, info in fields.items():
        if info.is_required():
            if name == "match_count":
                blob[name] = match_count
            elif name == "score_freq":
                blob[name] = {}
            else:
                blob[name] = 0.0
    return blob


class TestPat:
    def test_none_returns_none(self):
        assert _pat(None) is None

    def test_empty_dict_returns_none(self):
        assert _pat({}) is None

    def test_valid_blob(self):
        blob = _minimal_pattern_blob(10)
        result = _pat(blob)
        assert result is not None
        assert result.match_count == 10

    def test_partial_blob_returns_none(self):
        result = _pat({"match_count": 5})
        assert result is None


# ─── _trends_parse ──────────────────────────────────────────────────────────

def _trend_block(label: str = "Ev Formu") -> dict:
    return {
        "label": label,
        "sample_size": 5,
        "win_pct": 60.0,
        "draw_pct": 20.0,
        "loss_pct": 20.0,
        "kg_var_pct": 40.0,
        "over_25_pct": 60.0,
        "avg_goals_for": 1.8,
        "avg_goals_against": 0.8,
        "last_n_results": ["G", "G", "M", "B", "G"],
    }


class TestTrendsParse:
    def test_none_returns_none(self):
        assert _trends_parse(None) is None

    def test_empty_dict_returns_none(self):
        assert _trends_parse({}) is None

    def test_valid_trends_full(self):
        blob = {
            "home_form": _trend_block("Ev Formu"),
            "away_form": _trend_block("Dep Formu"),
            "h2h": _trend_block("H2H"),
        }
        result = _trends_parse(blob)
        assert result is not None
        assert result.home_form is not None
        assert result.home_form.win_pct == 60.0
        assert result.away_form is not None
        assert result.h2h is not None

    def test_partial_trends_ok(self):
        blob = {"home_form": _trend_block()}
        result = _trends_parse(blob)
        assert result is not None
        assert result.home_form is not None
        assert result.away_form is None

    def test_invalid_block_returns_none(self):
        blob = {"home_form": {"bad": "data"}}
        result = _trends_parse(blob)
        assert result is None


# ─── enqueue_bg_analysis ───────────────────────────────────────────────────

class TestEnqueueBgAnalysis:
    def test_no_queue_is_noop(self):
        import app.api.services as svc
        old_queue = svc.bg_queue
        svc.bg_queue = None
        # Should not raise
        enqueue_bg_analysis([SimpleNamespace(match_id="m1")])
        svc.bg_queue = old_queue

    def test_enqueue_adds_to_queue(self):
        import app.api.services as svc
        init_bg_queue()
        try:
            matches = [
                SimpleNamespace(match_id="m1"),
                SimpleNamespace(match_id="m2"),
            ]
            enqueue_bg_analysis(matches)
            assert svc.bg_queue.qsize() == 2
            assert "m1" in svc._bg_queued
            assert "m2" in svc._bg_queued
        finally:
            shutdown_bg_queue()

    def test_skip_cached_match(self):
        import app.api.services as svc
        init_bg_queue()
        try:
            cache_put("m1", _resp("m1"))
            enqueue_bg_analysis([SimpleNamespace(match_id="m1")])
            assert svc.bg_queue.qsize() == 0
        finally:
            shutdown_bg_queue()

    def test_skip_already_queued(self):
        import app.api.services as svc
        init_bg_queue()
        try:
            matches = [SimpleNamespace(match_id="m1")]
            enqueue_bg_analysis(matches)
            enqueue_bg_analysis(matches)
            assert svc.bg_queue.qsize() == 1
        finally:
            shutdown_bg_queue()


# ─── init/shutdown_bg_queue ────────────────────────────────────────────────

class TestBgQueueLifecycle:
    def test_init_creates_queue(self):
        import app.api.services as svc
        init_bg_queue()
        assert svc.bg_queue is not None
        shutdown_bg_queue()

    def test_shutdown_clears(self):
        import app.api.services as svc
        init_bg_queue()
        svc._bg_queued.add("leftover")
        shutdown_bg_queue()
        assert svc.bg_queue is None
        assert len(svc._bg_queued) == 0
