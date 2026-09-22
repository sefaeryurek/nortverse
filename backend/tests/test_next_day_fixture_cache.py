"""The next day's bulletin can be prepared without analyzing matches."""

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models import FixtureMatch
from app.pipeline import runner


@pytest.mark.asyncio
async def test_refresh_saves_only_fixture_data_and_retains_observed_scores(monkeypatch):
    day = date(2026, 9, 23)
    kickoff = datetime(2026, 9, 23, 18, tzinfo=timezone.utc)
    previous = SimpleNamespace(matches_json=[{
        "match_id": "101", "home_team": "Old", "away_team": "Away",
        "league_code": "ENG PR", "kickoff_time": kickoff.isoformat(),
        "score_status": "live", "score_home": 1, "score_away": 0,
    }])
    session = AsyncMock()
    session.get.return_value = previous

    @asynccontextmanager
    async def fake_session():
        yield session

    @asynccontextmanager
    async def fake_browser():
        yield object()

    fixture = FixtureMatch(
        match_id="101", home_team="New", away_team="Away",
        league_code="ENG PR", league_name="English Premier League", kickoff_time=kickoff,
    )
    monkeypatch.setattr(runner, "get_session", fake_session)
    monkeypatch.setattr(runner, "browser_context", fake_browser)
    fetch = AsyncMock(return_value=[fixture])
    monkeypatch.setattr(runner, "fetch_istanbul_fixture", fetch)
    analyze = AsyncMock()
    monkeypatch.setattr(runner, "fetch_match_detail", analyze)

    assert await runner.refresh_fixture_cache(day) == 1
    fetch.assert_awaited_once()
    analyze.assert_not_awaited()
    saved = session.merge.await_args.args[0]
    assert saved.date == day.isoformat()
    assert saved.matches_json[0]["home_team"] == "New"
    assert saved.matches_json[0]["score_status"] == "live"
    assert saved.matches_json[0]["score_home"] == 1


@pytest.mark.asyncio
async def test_refresh_drops_old_cup_rows_from_cache(monkeypatch):
    day = date(2026, 9, 23)
    kickoff = datetime(2026, 9, 23, 18, tzinfo=timezone.utc)
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(matches_json=[{
        "match_id": "456", "home_team": "Cup Home", "away_team": "Cup Away",
        "league_code": "Netherlands KNVB Beker", "kickoff_time": kickoff.isoformat(),
    }])

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(runner, "get_session", fake_session)
    assert await runner.save_fixture_cache(day, []) == 0
    assert session.merge.await_args.args[0].matches_json == []
