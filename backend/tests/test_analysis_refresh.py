import asyncio
from collections import OrderedDict
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api import services as svc
from app.api import routes_analysis


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(svc, "analysis_cache", OrderedDict())
    monkeypatch.setattr(svc, "_analysis_cached_at", {})
    monkeypatch.setattr(routes_analysis, "ANALYSIS_TIMEOUT", 0.02)


@pytest.mark.asyncio
async def test_refresh_timeout_cancels_scrape_and_keeps_previous_cache(monkeypatch):
    cancelled = asyncio.Event()

    async def stuck_scrape(match_id):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(routes_analysis, "do_analyze", stuck_scrape)
    svc.cache_put("123", "previous")
    with pytest.raises(HTTPException) as error:
        await routes_analysis.post_analyze("123")
    assert error.value.status_code == 504
    assert cancelled.is_set()
    assert svc.cache_get("123") == "previous"
    assert not svc.get_or_make_lock("123").locked()


@pytest.mark.asyncio
async def test_refresh_timeout_also_bounds_wait_for_lock(monkeypatch):
    scrape = AsyncMock()
    monkeypatch.setattr(routes_analysis, "do_analyze", scrape)
    lock = svc.get_or_make_lock("123")
    async with lock:
        with pytest.raises(HTTPException) as error:
            await routes_analysis.post_analyze("123")
        assert error.value.status_code == 504
        assert lock.locked()  # Another request's lock must remain owned.
    scrape.assert_not_called()


@pytest.mark.asyncio
async def test_successful_refresh_replaces_old_cache(monkeypatch):
    monkeypatch.setattr(routes_analysis, "do_analyze", AsyncMock(return_value="updated"))
    svc.cache_put("123", "previous")
    assert await routes_analysis.post_analyze("123") == "updated"
    assert svc.cache_get("123") == "updated"
