import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx
import pytest

from app.api import main as api
from app.api import services as svc


def test_analysis_cache_expires(monkeypatch):
    monkeypatch.setattr(svc.time, "monotonic", lambda: 1000)
    svc.cache_put("ttl", "old analysis")
    assert svc.cache_get("ttl") == "old analysis"
    monkeypatch.setattr(svc.time, "monotonic", lambda: 1000 + svc.ANALYSIS_CACHE_TTL)
    assert svc.cache_get("ttl") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/matches?limit=-1", "/api/matches?limit=0",
                                  "/api/analyze/not-a-match", "/api/match/abc"])
async def test_invalid_requests_do_not_reach_database(path):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://test") as client:
        response = await client.get(path)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_fixture_bad_date_not_cached():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://test") as client:
        response = await client.get("/api/fixture?date=bad-date")
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_live_lock_survives_cache_eviction(monkeypatch):
    monkeypatch.setattr(svc, "_CACHE_MAX", 1)
    svc.analysis_cache.clear()
    lock = svc.get_or_make_lock("1")
    async with lock:
        svc.cache_put("1", None)
        svc.cache_put("2", None)
        assert svc.get_or_make_lock("1") is lock
    svc.analysis_cache.clear()


@pytest.mark.asyncio
async def test_concurrent_analysis_scrapes_once(monkeypatch):
    svc.analysis_cache.clear()
    session = AsyncMock()
    from unittest.mock import MagicMock
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    @asynccontextmanager
    async def fake_session():
        yield session

    async def scrape(match_id):
        await asyncio.sleep(0)
        return "result"

    mock = AsyncMock(side_effect=scrape)
    monkeypatch.setattr(svc, "get_session", fake_session)
    monkeypatch.setattr(svc, "do_analyze", mock)
    assert await asyncio.gather(*(svc.analyze_and_cache("123") for _ in range(10))) == ["result"] * 10
    assert mock.await_count == 1
    svc.analysis_cache.clear()
