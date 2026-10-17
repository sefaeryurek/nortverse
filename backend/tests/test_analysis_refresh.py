import asyncio
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api import services as svc
from app.api import routes_analysis


def _fake_request(host: str = "127.0.0.1", headers: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers or {})


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(svc, "analysis_cache", OrderedDict())
    monkeypatch.setattr(svc, "_analysis_cached_at", {})
    monkeypatch.setattr(routes_analysis, "ANALYSIS_TIMEOUT", 0.02)
    routes_analysis._rate_buckets.clear()
    monkeypatch.setattr(routes_analysis, "_kickoff_of", AsyncMock(return_value=None))


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
        await routes_analysis.post_analyze(_fake_request(), "123")
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
            await routes_analysis.post_analyze(_fake_request(), "123")
        assert error.value.status_code == 504
        assert lock.locked()  # Another request's lock must remain owned.
    scrape.assert_not_called()


@pytest.mark.asyncio
async def test_successful_refresh_replaces_old_cache(monkeypatch):
    monkeypatch.setattr(routes_analysis, "do_analyze", AsyncMock(return_value="updated"))
    svc.cache_put("123", "previous")
    assert await routes_analysis.post_analyze(_fake_request(), "123") == "updated"
    assert svc.cache_get("123") == "updated"


@pytest.mark.asyncio
async def test_refresh_after_kickoff_is_rejected_and_keeps_prematch_analysis(monkeypatch):
    from datetime import datetime, timedelta, timezone
    scrape = AsyncMock()
    monkeypatch.setattr(routes_analysis, "do_analyze", scrape)
    monkeypatch.setattr(routes_analysis, "_kickoff_of",
                        AsyncMock(return_value=datetime.now(timezone.utc) - timedelta(minutes=5)))
    with pytest.raises(HTTPException) as error:
        await routes_analysis.post_analyze(_fake_request(), "123")
    assert error.value.status_code == 409
    scrape.assert_not_called()


def test_forwarded_ip_only_from_trusted_proxy(monkeypatch):
    monkeypatch.setattr(routes_analysis, "_TRUSTED_PROXIES", {"10.0.0.1"})
    headers = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}
    assert routes_analysis._client_ip(_fake_request("10.0.0.1", headers)) == "203.0.113.7"
    assert routes_analysis._client_ip(_fake_request("198.51.100.2", headers)) == "198.51.100.2"
