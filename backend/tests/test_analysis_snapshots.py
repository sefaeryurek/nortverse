from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.analysis import analyze_match
from app.analysis.snapshots import RULE_VERSION, build_ft_recommendations, prekickoff_picks
from app.api import routes_admin
from app.api import services
from app.db.models import Match
from app.models import MatchRawData
from app.pipeline import runner


NOW = datetime(2026, 9, 22, 10, tzinfo=timezone.utc)


def _pattern(count=30, result_1=70, over=68, btts=66):
    return {
        "match_count": count,
        "result_1_pct": result_1, "result_x_pct": 20, "result_2_pct": 10,
        "alt_25_pct": 100 - over, "ust_25_pct": over,
        "kg_var_pct": btts, "kg_yok_pct": 100 - btts,
    }


def test_fixed_rule_captures_only_qualifying_market_choices():
    picks = prekickoff_picks(
        analyzed_at=NOW, captured_at=NOW + timedelta(minutes=1), kickoff_time=NOW + timedelta(hours=2),
        league_name="Dutch Eredivisie",
        patterns={"pattern_ft_b": _pattern(), "pattern_ft_c": _pattern(count=1)},
    )

    assert RULE_VERSION == "ft-display-v2"
    assert [(p["archive"], p["market"], p["selection"]) for p in picks] == [
        ("archive_1", "result", "1"),
        ("archive_1", "over_25", "over"),
        ("archive_1", "btts", "yes"),
    ]
    assert all(p["match_count"] == 30 for p in picks)


def test_ineligible_analysis_never_creates_a_snapshot():
    args = dict(analyzed_at=NOW, captured_at=NOW + timedelta(minutes=1), kickoff_time=NOW + timedelta(hours=2),
                league_name="Dutch Eredivisie", patterns={"pattern_ft_b": _pattern()})
    assert prekickoff_picks(**{**args, "kickoff_time": NOW}) is None
    assert prekickoff_picks(**{**args, "kickoff_time": None}) is None
    assert prekickoff_picks(**{**args, "league_name": "Netherlands KNVB Beker"}) is None
    assert prekickoff_picks(**{**args, "league_name": "Netherlands KNVB Beker", "league_code": "HOL D1"}) is None
    assert prekickoff_picks(**{**args, "patterns": None}) is None


def test_eligible_analysis_without_a_pick_is_still_recorded():
    assert prekickoff_picks(
        analyzed_at=NOW, captured_at=NOW + timedelta(minutes=1), kickoff_time=NOW + timedelta(hours=2),
        league_name="Dutch Eredivisie",
        patterns={"pattern_ft_b": _pattern(result_1=40, over=52, btts=50)},
    ) == []


@pytest.mark.asyncio
async def test_db_first_analysis_freezes_missing_snapshot_before_kickoff(monkeypatch):
    session = AsyncMock()
    session.get.return_value = None

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(services, "get_session", fake_session)
    row = Match(
        match_id="123", home_team="Home", away_team="Away", league_code="ENG PR",
        league_name="English Premier League", analyzed_at=NOW,
        kickoff_time=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    session.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: row),
        MagicMock(rowcount=1),
    ]
    picks = await services._frozen_recommendations(row, {"pattern_ft_b": _pattern()})

    assert [pick["market"] for pick in picks] == ["result", "over_25", "btts"]
    statement = session.execute.await_args_list[1].args[0]
    assert "INSERT INTO analysis_snapshots" in str(statement.compile(dialect=postgresql.dialect()))
    assert statement.compile(dialect=postgresql.dialect()).params["analyzed_at"] == NOW


@pytest.mark.asyncio
async def test_cached_analysis_refreshes_snapshot_written_by_another_process(monkeypatch):
    picks = build_ft_recommendations({"pattern_ft_b": _pattern()})
    session = AsyncMock()
    session.get.return_value = MagicMock(picks=picks)

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(services, "get_session", fake_session)
    monkeypatch.setattr(services, "_snapshot_checked_at", {})
    monkeypatch.setattr(services, "_snapshot_finalized", set())
    cache_put = MagicMock()
    monkeypatch.setattr(services, "cache_put", cache_put)
    response = services.AnalyzeResponse(
        match_id="123", home_team="Home", away_team="Away", league_code="ENG PR", season="2026/2027",
        ht={"scores_1": [], "scores_x": [], "scores_2": []},
        half2={"scores_1": [], "scores_x": [], "scores_2": []},
        ft={"scores_1": [], "scores_x": [], "scores_2": []},
    )

    refreshed = await services._refresh_cached_recommendations(response)

    assert [item.model_dump() for item in refreshed.ft_recommendations] == picks
    cache_put.assert_called_once_with("123", refreshed)


@pytest.mark.asyncio
async def test_db_first_snapshot_rejects_stale_or_deleted_match(monkeypatch):
    session = AsyncMock()
    session.get.return_value = None
    session.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(services, "get_session", fake_session)
    row = Match(
        match_id="stale", home_team="Home", away_team="Away", league_code="ENG PR",
        league_name="English Premier League", analyzed_at=NOW,
        kickoff_time=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )

    assert await services._frozen_recommendations(row, {"pattern_ft_b": _pattern()}) == []
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_cached_analysis_does_not_query_after_snapshot_is_final(monkeypatch):
    monkeypatch.setattr(services, "_snapshot_finalized", {"123"})
    session_factory = MagicMock()
    monkeypatch.setattr(services, "get_session", session_factory)
    response = services.AnalyzeResponse(
        match_id="123", home_team="Home", away_team="Away", league_code="ENG PR", season="2026/2027",
        ht={"scores_1": [], "scores_x": [], "scores_2": []},
        half2={"scores_1": [], "scores_x": [], "scores_2": []},
        ft={"scores_1": [], "scores_x": [], "scores_2": []},
    )

    assert await services._refresh_cached_recommendations(response) is response
    session_factory.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_freezes_first_prekickoff_record_and_never_updates_it(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = MagicMock(rowcount=1)

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(runner, "get_session", fake_session)
    raw = MatchRawData(match_id="123", home_team="Home", away_team="Away",
                       league_code="ENG PR", kickoff_time=NOW + timedelta(hours=2))
    result = analyze_match(raw)
    result.analyzed_at = NOW
    await runner._upsert(result, raw, {"pattern_ft_b": _pattern()}, captured_at=NOW + timedelta(minutes=1))

    assert session.execute.await_count == 2
    statement = session.execute.await_args_list[1].args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "INSERT INTO analysis_snapshots" in sql
    assert "ON CONFLICT (match_id, rule_version) DO NOTHING" in sql
    assert statement.compile(dialect=postgresql.dialect()).params["picks"]


@pytest.mark.asyncio
async def test_upsert_after_kickoff_does_not_make_a_snapshot(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = MagicMock(rowcount=1)

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(runner, "get_session", fake_session)
    raw = MatchRawData(match_id="123", home_team="Home", away_team="Away",
                       league_code="ENG PR", kickoff_time=NOW)
    result = analyze_match(raw)
    result.analyzed_at = NOW + timedelta(minutes=1)
    await runner._upsert(result, raw, {"pattern_ft_b": _pattern()})

    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_validation_reports_only_aggregate_outcomes(monkeypatch):
    session = AsyncMock()
    session.execute.side_effect = [
        MagicMock(one=lambda: (12, 4)),
        MagicMock(all=lambda: [("archive_1", "result", 3, 2)]),
    ]

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(routes_admin, "get_session", fake_session)
    response = await routes_admin.analysis_validation()

    assert response.recorded == 12
    assert response.resolved == 4
    assert response.markets[0].model_dump() == {
        "archive": "archive_1", "market": "result", "evaluated": 3, "hits": 2,
    }
    assert session.execute.await_args_list[0].args[1] == {"rule_version": RULE_VERSION}
    query = str(session.execute.await_args_list[1].args[0])
    assert "jsonb_array_elements" in query
    assert "COALESCE(m.result_first_fetched_at, m.result_fetched_at) > s.kickoff_time" in query
