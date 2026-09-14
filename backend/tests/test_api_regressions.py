import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx
import pytest

from app.api import main as api


def test_analysis_cache_expires(monkeypatch):
    monkeypatch.setattr(api.time, "monotonic", lambda: 1000)
    api._cache_put("ttl", "old analysis")
    assert api._cache_get("ttl") == "old analysis"
    monkeypatch.setattr(api.time, "monotonic", lambda: 1000 + api.ANALYSIS_CACHE_TTL)
    assert api._cache_get("ttl") is None


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
    monkeypatch.setattr(api, "_CACHE_MAX", 1)
    api._analysis_cache.clear()
    lock = api._get_or_make_lock("1")
    async with lock:
        api._cache_put("1", None)
        api._cache_put("2", None)
        assert api._get_or_make_lock("1") is lock
    api._analysis_cache.clear()


@pytest.mark.asyncio
async def test_concurrent_analysis_scrapes_once(monkeypatch):
    api._analysis_cache.clear()
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
    monkeypatch.setattr(api, "get_session", fake_session)
    monkeypatch.setattr(api, "_do_analyze", mock)
    assert await asyncio.gather(*(api._analyze_and_cache("123") for _ in range(10))) == ["result"] * 10
    assert mock.await_count == 1
    api._analysis_cache.clear()
