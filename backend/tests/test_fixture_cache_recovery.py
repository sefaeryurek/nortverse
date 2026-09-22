from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api import routes_fixture as rf
from app.api import services as svc
from app.models import FixtureMatch


@pytest.fixture(autouse=True)
def no_live_source(monkeypatch):
    monkeypatch.setattr(rf, "get_live_snapshot", AsyncMock(return_value=None))


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
    monkeypatch.setattr(rf, "fetch_istanbul_fixture", fetch)
    save = AsyncMock()
    monkeypatch.setattr(rf, "save_fixture_cache", save)
    assert await rf.fixture(None) == []
    fetch.assert_awaited_once()
    save.assert_awaited_once()


@pytest.mark.asyncio
async def test_scraped_bulletin_hides_cup_but_keeps_competition_for_direct_link(monkeypatch):
    session = AsyncMock()
    session.get.return_value = None

    @asynccontextmanager
    async def get_session():
        yield session

    cup = FixtureMatch(match_id="456", home_team="Cup Home", away_team="Cup Away",
                       league_code="HOL D3", league_name="Netherlands KNVB Beker")
    league = FixtureMatch(match_id="123", home_team="Home", away_team="Away",
                          league_code="ENG PR", league_name="English Premier League")
    monkeypatch.setattr(rf, "get_session", get_session)
    monkeypatch.setattr(rf, "fixture_cache", {})
    monkeypatch.setattr(rf, "fetch_istanbul_fixture", AsyncMock(return_value=[cup, league]))
    save = AsyncMock()
    monkeypatch.setattr(rf, "save_fixture_cache", save)

    result = await rf.fixture(None)

    assert [match.match_id for match in result] == ["123"]
    assert [match.match_id for match in save.await_args.args[1]] == ["456", "123"]


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
    monkeypatch.setattr(rf, "fetch_istanbul_fixture", fetch)
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
    monkeypatch.setattr(rf, "fetch_istanbul_fixture", fetch)

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


@pytest.mark.asyncio
async def test_scraper_failure_returns_service_unavailable(monkeypatch):
    session = AsyncMock()
    session.get.return_value = None

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(rf, "get_session", get_session)
    monkeypatch.setattr(rf, "fixture_cache", {})
    monkeypatch.setattr(rf, "fetch_istanbul_fixture", AsyncMock(side_effect=RuntimeError("browser unavailable")))
    with pytest.raises(HTTPException) as error:
        await rf.fixture(None)
    assert error.value.status_code == 503
