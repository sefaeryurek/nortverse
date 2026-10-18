"""Maç öncesi (v4) kararın bir kez dondurulması: hazır maçlar, DB-first analiz, önbellek ve upsert yolları."""

from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.analysis import analyze_match
from app.analysis import persist
from app.analysis import prematch_v4
from app.analysis.live_model import CondTable
from app.api import services
from app.db.models import Match
from app.models import MatchRawData
from app.pipeline import runner

NOW = datetime(2026, 9, 24, 10, tzinfo=timezone.utc)


def _empty_cond_table(monkeypatch):
    """v4 yakalama lig ortalaması için COND tablosu ister; boş tablo ≈ eşit dağılım."""
    table = CondTable(cutoff=NOW, prior_from=NOW)
    monkeypatch.setattr(prematch_v4, "get_cond_table", AsyncMock(return_value=table))
    return table


def _sql(call) -> str:
    return str(call.args[0].compile(dialect=postgresql.dialect()))


def _pattern(count=30, result_1=70, over=68, btts=66):
    return {
        "match_count": count,
        "result_1_pct": result_1, "result_x_pct": 20, "result_2_pct": 10,
        "alt_25_pct": 100 - over, "ust_25_pct": over,
        "kg_var_pct": btts, "kg_yok_pct": 100 - btts,
    }

ANALYZED_AT = datetime(2026, 9, 24, 9, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_prepared_capture_writes_patterns_and_freezes_v4_bundle(monkeypatch):
    prepared = SimpleNamespace(
        match_id="prepared-1",
        analyzed_at=ANALYZED_AT,
        kickoff_time=datetime(2099, 1, 1, 18, tzinfo=timezone.utc),
        league_name="English Premier League",
        league_code="ENG PR",
        ht_scores_1=[], ht_scores_x=[], ht_scores_2=[],
        h2_scores_1=[], h2_scores_x=[], h2_scores_2=[],
        ft_scores_1=[], ft_scores_x=[], ft_scores_2=[], ft_all_ratios={},
    )
    listing_session = AsyncMock()
    listing_session.execute.return_value = MagicMock(all=lambda: [prepared])
    capture_session = AsyncMock()
    capture_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: prepared),
        MagicMock(rowcount=1),
        MagicMock(rowcount=5),
    ]
    sessions = iter((listing_session, capture_session))

    @asynccontextmanager
    async def fake_session():
        yield next(sessions)

    patterns = {"pattern_ft_b": _pattern()}
    compute = AsyncMock(return_value=patterns)
    write = AsyncMock()
    monkeypatch.setattr("app.db.connection.get_session", fake_session)
    monkeypatch.setattr(persist, "compute_all_patterns", compute)
    monkeypatch.setattr(persist, "update_match_patterns", write)
    _empty_cond_table(monkeypatch)

    count = await prematch_v4.capture_prepared_recommendations(date(2099, 1, 1))

    assert count == 1
    assert compute.await_args.kwargs["as_of"] == ANALYZED_AT
    write.assert_awaited_once()  # ekran ile dondurulan seçim aynı pattern'den
    calls = capture_session.execute.await_args_list
    assert "INSERT INTO analysis_snapshots" in _sql(calls[1])
    assert "INSERT INTO prediction_ledger" in _sql(calls[2])


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
        league_name="English Premier League", analyzed_at=ANALYZED_AT,
        kickoff_time=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    session.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: row),
        MagicMock(rowcount=1),
        MagicMock(rowcount=5),
    ]
    _empty_cond_table(monkeypatch)
    picks = await services._frozen_recommendations(row, {"pattern_ft_b": _pattern()})

    assert [pick["market"] for pick in picks] == ["result"]
    statement = session.execute.await_args_list[1].args[0]
    assert "INSERT INTO analysis_snapshots" in str(statement.compile(dialect=postgresql.dialect()))
    assert statement.compile(dialect=postgresql.dialect()).params["analyzed_at"] == ANALYZED_AT


@pytest.mark.asyncio
async def test_cached_analysis_refreshes_snapshot_written_by_another_process(monkeypatch):
    picks = prematch_v4.build_v4_recommendations(
        {"pattern_ft_b": _pattern()}, {"1": 1 / 3, "X": 1 / 3, "2": 1 / 3})
    session = AsyncMock()
    session.get.return_value = MagicMock(picks=picks)

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(services, "get_session", fake_session)
    monkeypatch.setattr(services, "_snapshot_checked_at", {})
    monkeypatch.setattr(services, "_snapshot_finalized", OrderedDict())
    cache_put = MagicMock()
    monkeypatch.setattr(services, "cache_put", cache_put)
    response = services.AnalyzeResponse(
        match_id="123", home_team="Home", away_team="Away", league_code="ENG PR", season="2026/2027",
        ht={"scores_1": [], "scores_x": [], "scores_2": []},
        half2={"scores_1": [], "scores_x": [], "scores_2": []},
        ft={"scores_1": [], "scores_x": [], "scores_2": []},
    )

    refreshed = await services._refresh_cached_recommendations(response)

    assert [item.model_dump(exclude_none=True) for item in refreshed.ft_recommendations] == [
        {k: v for k, v in pick.items() if v is not None} for pick in picks
    ]
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
    monkeypatch.setattr(services, "_snapshot_finalized", OrderedDict({f"{services.RULE_VERSION}:123": 0.0}))
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
    session.begin_nested = MagicMock(return_value=AsyncMock())
    session.execute.side_effect = [MagicMock(rowcount=1) for _ in range(6)]

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(runner, "get_session", fake_session)
    _empty_cond_table(monkeypatch)
    raw = MatchRawData(match_id="123", home_team="Home", away_team="Away",
                       league_code="ENG PR", kickoff_time=NOW + timedelta(hours=2))
    result = analyze_match(raw)
    result.analyzed_at = NOW
    await runner._upsert(result, raw, {"pattern_ft_b": _pattern()}, captured_at=NOW + timedelta(minutes=1))

    calls = session.execute.await_args_list
    sql = _sql(calls[1])
    assert "INSERT INTO analysis_snapshots" in sql
    assert "ON CONFLICT (match_id, rule_version) DO NOTHING" in sql
    assert calls[1].args[0].compile(dialect=postgresql.dialect()).params["picks"]
    assert "INSERT INTO prediction_ledger" in _sql(calls[2])


@pytest.mark.asyncio
async def test_upsert_after_kickoff_does_not_make_a_snapshot(monkeypatch):
    session = AsyncMock()
    session.begin_nested = MagicMock(return_value=AsyncMock())
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
