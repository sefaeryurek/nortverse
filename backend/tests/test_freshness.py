"""Süreç içi önbelleklerin yeni sonuçla yenilenme sinyali."""

from unittest.mock import AsyncMock

import pytest

from app.analysis import freshness
from app.analysis.freshness import ResultsWatch


@pytest.mark.asyncio
async def test_unmarked_cache_is_stale():
    assert await ResultsWatch().stale() is True


@pytest.mark.asyncio
async def test_checks_db_at_most_once_per_interval(monkeypatch):
    marker = AsyncMock(return_value=(10, "t1"))
    monkeypatch.setattr(freshness, "results_marker", marker)
    watch = ResultsWatch(interval=300)
    watch.mark((10, "t1"))
    assert await watch.stale() is False
    marker.assert_not_awaited()  # aralık dolmadı → DB'ye gidilmez


@pytest.mark.asyncio
async def test_new_results_make_cache_stale(monkeypatch):
    monkeypatch.setattr(freshness, "results_marker", AsyncMock(return_value=(11, "t2")))
    watch = ResultsWatch(interval=0)
    watch.mark((10, "t1"))
    assert await watch.stale() is True


@pytest.mark.asyncio
async def test_unchanged_results_keep_cache(monkeypatch):
    monkeypatch.setattr(freshness, "results_marker", AsyncMock(return_value=(10, "t1")))
    watch = ResultsWatch(interval=0)
    watch.mark((10, "t1"))
    assert await watch.stale() is False
