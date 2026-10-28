import asyncio
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api import ratelimit, routes_analysis
from app.api import services as svc


def _fake_request(host: str = "127.0.0.1", headers: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers or {})


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(svc, "analysis_cache", OrderedDict())
    monkeypatch.setattr(svc, "_analysis_cached_at", {})
    monkeypatch.setattr(routes_analysis, "ANALYSIS_TIMEOUT", 0.02)
    ratelimit.reset()
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


def test_rate_limit_keys_by_user_not_forwarded_header():
    """Sprint 94 E3: X-Forwarded-For taklit edilebilir, tüm trafik 127.0.0.1 — sınır kullanıcıya göre."""
    from app.auth import AuthUser

    def req(user, forwarded):
        r = _fake_request("127.0.0.1", {"x-forwarded-for": forwarded})
        r.state = SimpleNamespace(user=user)
        return r

    alice, bob = AuthUser(1, "a", False), AuthUser(2, "b", False)
    assert ratelimit.client_key(req(alice, "203.0.113.7")) == ratelimit.client_key(req(alice, "198.51.100.2"))
    assert ratelimit.client_key(req(alice, "x")) != ratelimit.client_key(req(bob, "x"))
    for i in range(3):
        ratelimit.check_rate(req(alice, f"10.0.0.{i}"), "t", 3)  # başlığı değiştirmek sayacı sıfırlamaz
    with pytest.raises(HTTPException) as error:
        ratelimit.check_rate(req(alice, "10.9.9.9"), "t", 3)
    assert error.value.status_code == 429
    ratelimit.check_rate(req(bob, "10.0.0.1"), "t", 3)  # başka kullanıcı etkilenmez
