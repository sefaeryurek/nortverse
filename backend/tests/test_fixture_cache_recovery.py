from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api import routes_fixture as rf
from app.api import services as svc


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, [None], [{"match_id": "123"}], "bad"])
async def test_invalid_cache_recovers_by_fetching_fixture(monkeypatch, payload):
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(cached_at=datetime.now(timezone.utc), matches_json=payload)

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(rf, "get_session", get_session)
    monkeypatch.setattr(rf, "fixture_cache", {})
    monkeypatch.setattr(svc, "bg_queue", None)
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(rf, "fetch_fixture", fetch)
    assert await rf.fixture(None) == []
    fetch.assert_awaited_once()
    session.merge.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_naive_cache_timestamp_uses_utc(monkeypatch):
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(cached_at=datetime.now(timezone.utc).replace(tzinfo=None),
                                              matches_json=[])

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(rf, "get_session", get_session)
    monkeypatch.setattr(rf, "fixture_cache", {})
    monkeypatch.setattr(svc, "bg_queue", None)
    fetch = AsyncMock()
    monkeypatch.setattr(rf, "fetch_fixture", fetch)
    assert await rf.fixture(None) == []
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_old_daily_fixture_cache_returns_without_scraping(monkeypatch):
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(
        cached_at=datetime.now(timezone.utc) - timedelta(hours=8),
        matches_json=[{
            "match_id": "123", "home_team": "Home", "away_team": "Away",
            "league_code": "ENG PR", "league_name": "English Premier League",
            "kickoff_time": None,
        }],
    )

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(rf, "get_session", get_session)
    monkeypatch.setattr(rf, "fixture_cache", {})
    fetch = AsyncMock()
    monkeypatch.setattr(rf, "fetch_fixture", fetch)

    result = await rf.fixture(None)
    assert [match.match_id for match in result] == ["123"]
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_fixture_cache_hit_does_not_queue_all_matches_for_analysis(monkeypatch):
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(
        cached_at=datetime.now(timezone.utc),
        matches_json=[{
            "match_id": "123", "home_team": "Home", "away_team": "Away",
            "league_code": "ENG PR", "league_name": "English Premier League",
            "kickoff_time": None,
        }],
    )

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(rf, "get_session", get_session)
    monkeypatch.setattr(rf, "fixture_cache", {})
    svc.init_bg_queue()
    try:
        assert len(await rf.fixture(None)) == 1
        assert svc.bg_queue.qsize() == 0
    finally:
        svc.shutdown_bg_queue()
