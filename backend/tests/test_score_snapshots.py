from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.analysis.score_snapshots import SCORE_RULE_VERSION, capture_score_snapshot, score_shortlist
from app.api import routes_admin


NOW = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)


def test_score_shortlist_preserves_order_and_deduplicates():
    assert score_shortlist(["1-0", "2-1"], ["1-0"], ["0-0"]) == ["1-0", "2-1", "0-0"]
    with pytest.raises(ValueError):
        score_shortlist(["31-0"])


def test_paired_interval_accounts_for_paired_difference_range():
    difference, low, high = routes_admin.paired_coverage_interval(20, 10, 100)
    assert difference == pytest.approx(10.0)
    assert low == pytest.approx(-17.16, abs=0.01)
    assert high == pytest.approx(37.16, abs=0.01)


@pytest.mark.asyncio
async def test_capture_uses_only_prior_confirmed_results_and_equal_baseline():
    session = AsyncMock()
    session.get.return_value = None
    session.execute.side_effect = [
        MagicMock(all=lambda: [("1-0", 8), ("0-0", 7)]),
        MagicMock(rowcount=1),
    ]
    saved = await capture_score_snapshot(
        session, match_id="123", analyzed_at=NOW, captured_at=NOW + timedelta(minutes=5),
        kickoff_time=NOW + timedelta(hours=2), league_name="English Premier League",
        league_code="ENG PR", model_scores=["2-1", "0-0"],
    )
    assert saved
    query = str(session.execute.await_args_list[0].args[0].compile(dialect=postgresql.dialect()))
    assert "coalesce(matches.result_first_fetched_at, matches.result_fetched_at) <= " in query
    assert "coalesce(matches.result_first_fetched_at, matches.result_fetched_at) > matches.kickoff_time" in query
    assert "matches.match_id != " in query
    statement = session.execute.await_args_list[1].args[0]
    assert statement.compile(dialect=postgresql.dialect()).params["baseline_scores"] == ["1-0", "0-0"]
    assert "ON CONFLICT (match_id, rule_version) DO NOTHING" in str(statement.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
async def test_capture_never_backfills_after_kickoff_or_invents_short_baseline():
    session = AsyncMock()
    session.get.return_value = None
    assert not await capture_score_snapshot(
        session, match_id="123", analyzed_at=NOW, captured_at=NOW + timedelta(hours=2),
        kickoff_time=NOW + timedelta(hours=1), league_name="English Premier League",
        league_code="ENG PR", model_scores=["1-0"],
    )
    session.get.assert_not_awaited()
    session.execute.side_effect = [MagicMock(all=lambda: [("1-0", 8)]), MagicMock(rowcount=1)]
    assert await capture_score_snapshot(
        session, match_id="123", analyzed_at=NOW, captured_at=NOW + timedelta(minutes=5),
        kickoff_time=NOW + timedelta(hours=2), league_name="English Premier League",
        league_code="ENG PR", model_scores=["1-0", "0-0"],
    )
    statement = session.execute.await_args_list[1].args[0]
    assert statement.compile(dialect=postgresql.dialect()).params["baseline_scores"] is None


@pytest.mark.asyncio
async def test_score_validation_uses_frozen_lists_and_confirmed_outcomes(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = MagicMock(one=lambda: (12, 4, 3, 2, 1, 1, 2, 1, 0, 1, 0))

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(routes_admin, "get_session", fake_session)
    response = await routes_admin.score_validation()
    assert response.rule_version == SCORE_RULE_VERSION
    assert (response.recorded, response.resolved, response.paired) == (12, 4, 2)
    assert (response.paired_model_hits, response.baseline_hits) == (1, 2)
    query = str(session.execute.await_args.args[0])
    assert "s.captured_at < s.kickoff_time" in query
    assert "COALESCE(m.result_first_fetched_at, m.result_fetched_at) > s.kickoff_time" in query
    assert "baseline_scores IS NOT NULL" in query
