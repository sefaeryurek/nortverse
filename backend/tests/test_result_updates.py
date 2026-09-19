from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import FixtureCache, Match
from app.models import MatchRawData
from app.pipeline import runner
from app.scraper.fixture_scores import FixtureScore


def raw(**changes):
    return MatchRawData(**(dict(match_id="123", home_team="A", away_team="B", league_code="ENG PR",
                               actual_ft_home=2, actual_ft_away=1) | changes))


def existing():
    return Match(actual_ft_home=2, actual_ft_away=1, actual_ht_home=1, actual_ht_away=0,
                 actual_h2_home=1, actual_h2_away=1)


def test_missing_halves_preserved_when_final_score_unchanged():
    scores = runner._merge_result_scores(raw(), existing())
    assert (scores["actual_ht_home"], scores["actual_ht_away"]) == (1, 0)
    assert (scores["actual_h2_home"], scores["actual_h2_away"]) == (1, 1)


def test_corrected_final_score_does_not_keep_unverified_old_halves():
    scores = runner._merge_result_scores(raw(actual_ft_home=3), existing())
    assert scores["actual_ft_home"] == 3
    assert all(scores[key] is None for key in scores if "_ft_" not in key)


def test_new_first_half_replaces_old_and_derives_second_half():
    scores = runner._merge_result_scores(raw(actual_ht_home=0, actual_ht_away=1), existing())
    assert (scores["actual_h2_home"], scores["actual_h2_away"]) == (2, 0)


@pytest.mark.parametrize("changes", [
    {"actual_ft_home": -1}, {"actual_ht_home": 3, "actual_ht_away": 0},
    {"actual_ht_home": 1}, {"actual_ht_home": 0, "actual_ht_away": 0,
                              "actual_h2_home": 1, "actual_h2_away": 0},
])
def test_invalid_score_updates_rejected(changes):
    with pytest.raises(ValueError):
        runner._merge_result_scores(raw(**changes), existing())


@pytest.mark.asyncio
async def test_validation_failures_are_not_retried():
    operation = AsyncMock(side_effect=ValueError("bad input"))
    with pytest.raises(ValueError):
        await runner._with_retry(operation, "test")
    operation.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_fixture_or_match_does_not_scrape(monkeypatch):
    session = AsyncMock()
    selected = MagicMock()
    selected.scalars.return_value.all.return_value = []
    session.execute.return_value = selected
    session.get.return_value = None

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(runner, "get_session", get_session)
    fetch = AsyncMock()
    monkeypatch.setattr(runner, "fetch_fixture_scores", fetch)
    result = await runner.update_results(date(2026, 9, 14))
    assert result["updated"] == 0
    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_final_fixture_score_updates_all_results_without_detail_scrape(monkeypatch):
    session = AsyncMock()
    session.get.return_value = FixtureCache(
        date="2026-09-14", cached_at=datetime.now(timezone.utc),
        matches_json=[{"match_id": "123", "home_team": "A", "away_team": "B",
                       "league_code": "ENG PR", "kickoff_time": "2026-09-14T12:00:00+00:00"}],
    )
    selected = MagicMock()
    selected.scalars.return_value.all.return_value = []
    session.execute.return_value = selected

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(runner, "get_session", get_session)
    fetch = AsyncMock(return_value={"123": FixtureScore("123", "finished", 2, 1, 1, 0)})
    monkeypatch.setattr(runner, "fetch_fixture_scores", fetch)
    result = await runner.update_results(date(2026, 9, 14))
    assert result["updated"] == 1
    assert result["not_finished"] == 0
    fetch.assert_awaited_once()
    assert session.execute.await_count == 2  # select + one fixture-cache write


@pytest.mark.asyncio
async def test_late_istanbul_score_is_read_from_next_source_day(monkeypatch):
    session = AsyncMock()
    session.get.return_value = FixtureCache(
        date="2026-09-14", cached_at=datetime.now(timezone.utc),
        matches_json=[{"match_id": "123", "home_team": "A", "away_team": "B",
                       "league_code": "ENG PR", "kickoff_time": "2026-09-14T20:00:00+00:00"}],
    )
    selected = MagicMock()
    selected.scalars.return_value.all.return_value = []
    session.execute.return_value = selected

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(runner, "get_session", get_session)
    fetch = AsyncMock(side_effect=[{}, {"123": FixtureScore("123", "finished", 2, 1)}])
    monkeypatch.setattr(runner, "fetch_fixture_scores", fetch)
    result = await runner.update_results(date(2026, 9, 14))
    assert result["updated"] == 1
    assert [call.args[0] for call in fetch.await_args_list] == [date(2026, 9, 14), date(2026, 9, 15)]


def test_finished_score_is_not_downgraded_by_later_live_snapshot():
    old = [{"match_id": "123", "score_status": "finished", "score_home": 2, "score_away": 1}]
    merged = runner._merge_fixture_scores(
        old, {"123": FixtureScore("123", "live", 1, 1)}, datetime.now(timezone.utc))
    assert merged[0]["score_status"] == "finished"
    assert (merged[0]["score_home"], merged[0]["score_away"]) == (2, 1)
