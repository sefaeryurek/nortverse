import asyncio
from collections import OrderedDict
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api import main as api


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(api, "_analysis_cache", OrderedDict())
    monkeypatch.setattr(api, "_analysis_cached_at", {})
    monkeypatch.setattr(api, "ANALYSIS_TIMEOUT", 0.02)


@pytest.mark.asyncio
async def test_refresh_timeout_cancels_scrape_and_keeps_previous_cache(monkeypatch):
    cancelled = asyncio.Event()

    async def stuck_scrape(match_id):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(api, "_do_analyze", stuck_scrape)
    api._cache_put("123", "previous")
    with pytest.raises(HTTPException) as error:
        await api.post_analyze("123")
    assert error.value.status_code == 504
    assert cancelled.is_set()
    assert api._cache_get("123") == "previous"
    assert not api._get_or_make_lock("123").locked()


@pytest.mark.asyncio
async def test_refresh_timeout_also_bounds_wait_for_lock(monkeypatch):
    scrape = AsyncMock()
    monkeypatch.setattr(api, "_do_analyze", scrape)
    lock = api._get_or_make_lock("123")
    async with lock:
        with pytest.raises(HTTPException) as error:
            await api.post_analyze("123")
        assert error.value.status_code == 504
        assert lock.locked()  # Another request's lock must remain owned.
    scrape.assert_not_called()


@pytest.mark.asyncio
async def test_successful_refresh_replaces_old_cache(monkeypatch):
    monkeypatch.setattr(api, "_do_analyze", AsyncMock(return_value="updated"))
    api._cache_put("123", "previous")
    assert await api.post_analyze("123") == "updated"
    assert api._cache_get("123") == "updated"
