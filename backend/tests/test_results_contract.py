from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api import routes_results as rr
from app.db.models import FixtureCache, Match


@pytest.mark.asyncio
async def test_results_keep_scheduled_and_unconfirmed_matches(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [Match(match_id=str(i), home_team="A", away_team="B", league_code="ENG PR",
                  kickoff_time=kickoff, actual_ft_home=h, actual_ft_away=a)
            for i, (kickoff, h, a) in enumerate([
                (now + timedelta(hours=1), None, None),
                (now - timedelta(minutes=10), None, None),
                (now - timedelta(hours=4), None, None),
                (now - timedelta(hours=4), 2, 1),
            ])]
    result = MagicMock()
    result.all.return_value = rows
    session = AsyncMock()
    session.execute.return_value = result
    session.get.return_value = None

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(rr, "get_session", fake_session)
    matches = await rr.get_results("2026-09-14")
    by_id = {match.match_id: match for match in matches}
    assert {match_id: match.status for match_id, match in by_id.items()} == {
        "0": "scheduled", "1": "pending", "2": "pending", "3": "finished",
    }
    assert by_id["3"].result == "1"
    assert all(match.result is None for match_id, match in by_id.items() if match_id != "3")


@pytest.mark.asyncio
async def test_results_include_fixture_without_analysis_and_keep_live_score_unconfirmed(monkeypatch):
    now = datetime.now(timezone.utc)
    session = AsyncMock()
    session.get.return_value = FixtureCache(
        date="2026-09-14", cached_at=now,
        matches_json=[{
            "match_id": "123", "home_team": "Home", "away_team": "Away",
            "league_code": "English Premier League", "league_name": "English Premier League",
            "kickoff_time": "2026-09-14T12:00:00+00:00",
            "score_status": "live", "score_home": 2, "score_away": 1,
            "score_checked_at": now.isoformat(),
        }],
    )
    selected = MagicMock()
    selected.all.return_value = []
    session.execute.return_value = selected

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(rr, "get_session", fake_session)
    matches = await rr.get_results("2026-09-14")
    assert len(matches) == 1
    assert matches[0].status == "live"
    assert (matches[0].live_home, matches[0].live_away) == (2, 1)
    assert matches[0].actual_ft_home is None
    assert matches[0].result is None


@pytest.mark.asyncio
async def test_results_exclude_fixture_from_neighboring_istanbul_day(monkeypatch):
    session = AsyncMock()
    session.get.return_value = FixtureCache(
        date="2026-09-14", cached_at=datetime.now(timezone.utc),
        matches_json=[{"match_id": "late", "home_team": "A", "away_team": "B",
                       "league_code": "ENG PR", "kickoff_time": "2026-09-14T21:00:00+00:00"}],
    )
    selected = MagicMock()
    selected.all.return_value = []
    session.execute.return_value = selected

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(rr, "get_session", fake_session)
    assert await rr.get_results("2026-09-14") == []


@pytest.mark.asyncio
async def test_katman_a_coverage_requires_exact_final_score(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [
        Match(match_id="hit", home_team="A", away_team="B", league_code="ENG PR",
              kickoff_time=now - timedelta(hours=4), actual_ft_home=2, actual_ft_away=1,
              ft_scores_1=["2-1", "1-0"]),
        Match(match_id="miss", home_team="C", away_team="D", league_code="ENG PR",
              kickoff_time=now - timedelta(hours=4), actual_ft_home=2, actual_ft_away=1,
              ft_scores_1=["1-0"]),
    ]
    session = AsyncMock()
    session.get.return_value = None
    selected = MagicMock()
    selected.all.return_value = rows
    session.execute.return_value = selected

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(rr, "get_session", fake_session)
    by_id = {match.match_id: match for match in await rr.get_results("2026-09-14")}
    assert by_id["hit"].katman_a_covered is True
    assert by_id["miss"].katman_a_covered is False
