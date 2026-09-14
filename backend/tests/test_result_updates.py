from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import Match
from app.models import MatchRawData
from app.pipeline import runner


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
@pytest.mark.parametrize("ids", [[], ["123"]])
async def test_empty_or_deleted_matches_are_not_counted_as_updated(monkeypatch, ids):
    session = AsyncMock()
    selected = MagicMock()
    selected.scalars.return_value.all.return_value = ids
    missing = MagicMock()
    missing.scalar_one_or_none.return_value = None
    session.execute.side_effect = [selected, missing]

    @asynccontextmanager
    async def get_session():
        yield session

    browser_calls = []

    @asynccontextmanager
    async def browser():
        browser_calls.append(True)
        yield object()

    monkeypatch.setattr(runner, "get_session", get_session)
    monkeypatch.setattr(runner, "browser_context", browser)
    monkeypatch.setattr(runner, "fetch_match_detail", AsyncMock(return_value=raw()))
    result = await runner.update_results(date(2026, 9, 14))
    assert result["updated"] == 0
    assert result["skipped"] == len(ids)
    assert len(browser_calls) == bool(ids)
    assert session.execute.await_count == (2 if ids else 1)
