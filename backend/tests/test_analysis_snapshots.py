"""Maç öncesi (v4) kararın bir kez dondurulması: hazır maçlar, DB-first analiz, önbellek ve upsert yolları."""

from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
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


@pytest.fixture(autouse=True)
def _not_started(monkeypatch):
    """Bu dosyadaki sahte oturumlar "maç başlamış mı" sorgularını bilmez; koruma ayrı test edilir."""
    monkeypatch.setattr(prematch_v4, "match_already_started", AsyncMock(return_value=None))


def _empty_cond_table(monkeypatch):
    """v4 yakalama lig ortalaması için COND tablosu ister; boş tablo ≈ eşit dağılım."""
    table = CondTable(cutoff=NOW, prior_from=NOW)
    monkeypatch.setattr(prematch_v4, "get_cond_table", AsyncMock(return_value=table))
    return table


def _v5_model(monkeypatch):
    """v5 için sabit takım modeli: ev sahibi açık favori (lig ortalaması ≈ eşit dağılım)."""
    from app.analysis import live_model, live_poisson, prematch_v5

    monkeypatch.setattr(live_model, "get_cond_table", prematch_v4.get_cond_table)  # _empty_cond_table ile aynı
    monkeypatch.setattr(live_poisson, "get_poisson_model", AsyncMock(return_value=object()))
    monkeypatch.setattr(prematch_v5, "match_probabilities", lambda *_: {
        "result": {"1": 0.7, "X": 0.2, "2": 0.1}, "over25": 0.6, "btts": 0.4,
        "lambda": {"home": 2.0, "away": 0.8}, "rho": -0.05, "train_n": 500,
    })


TEAMS = MagicMock(first=lambda: SimpleNamespace(home_team="Home", away_team="Away",
                                                league_name="English Premier League"))


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
# Karar en erken başlamadan 48 saat önce dondurulur → servis yolları gerçek saatle çalıştığı için yakın gelecek.
SOON = datetime.now(timezone.utc) + timedelta(hours=6)


@pytest.mark.asyncio
async def test_prepared_capture_writes_patterns_and_freezes_v4_bundle(monkeypatch):
    prepared = SimpleNamespace(
        match_id="prepared-1",
        analyzed_at=ANALYZED_AT,
        kickoff_time=SOON,
        league_name="English Premier League",
        league_code="ENG PR",
        ht_scores_1=[], ht_scores_x=[], ht_scores_2=[],
        h2_scores_1=[], h2_scores_x=[], h2_scores_2=[],
        ft_scores_1=[], ft_scores_x=[], ft_scores_2=[], ft_all_ratios={},
    )
    listing_session = AsyncMock()
    listing_session.execute.return_value = MagicMock(all=lambda: [prepared])
    capture_session = AsyncMock()
    capture_session.get.return_value = None
    capture_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: prepared),
        MagicMock(rowcount=1),   # v4 snapshot (gölge)
        MagicMock(rowcount=5),   # v4 defter
        TEAMS,                   # v5 için takımlar
        MagicMock(rowcount=1),   # v5 snapshot (ekranda)
        MagicMock(rowcount=3),   # v5 defter
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
    _v5_model(monkeypatch)

    count = await prematch_v4.capture_prepared_recommendations(SOON.date())

    assert count == 1
    assert compute.await_args.kwargs["as_of"] == ANALYZED_AT
    write.assert_awaited_once()  # ekran ile dondurulan seçim aynı pattern'den
    calls = capture_session.execute.await_args_list
    assert "INSERT INTO analysis_snapshots" in _sql(calls[1])
    assert "INSERT INTO prediction_ledger" in _sql(calls[2])
    assert "INSERT INTO analysis_snapshots" in _sql(calls[4])
    assert "ft-display-v5" in str(calls[4].args[0].compile(dialect=postgresql.dialect()).params)
    assert "INSERT INTO prediction_ledger" in _sql(calls[5])


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
        kickoff_time=SOON,
    )
    session.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: row),
        MagicMock(rowcount=1),
        MagicMock(rowcount=5),
        TEAMS,
        MagicMock(rowcount=1),
        MagicMock(rowcount=3),
    ]
    _empty_cond_table(monkeypatch)
    _v5_model(monkeypatch)
    picks = await services._frozen_recommendations(row, {"pattern_ft_b": _pattern()})

    assert [pick["market"] for pick in picks] == ["result"]
    assert picks[0]["recommendation_id"].startswith("ft-display-v5")
    assert picks[0]["archive"] == "model" and picks[0]["agreement"] == 1   # v4 de ev sahibi diyor
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


def test_started_evidence_ignores_placeholder_db_kickoff():
    """DB saati yer tutucu (yarın) olsa bile bültenin güncel kaydı maçın geçtiğini gösteriyorsa kayıt yok."""
    captured = datetime(2026, 10, 18, 10, 53, tzinfo=timezone.utc)
    played = datetime(2026, 10, 17, 13, 0, tzinfo=timezone.utc).isoformat()
    future = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc).isoformat()
    ev = prematch_v4.started_evidence
    common = dict(match_id="3026756", captured_at=captured)
    assert ev(actual_ft_home=None, ht_observed=False, cache_rows=[], **common) is None
    assert ev(actual_ft_home=1, ht_observed=False, cache_rows=[], **common) == "result_known"
    assert ev(actual_ft_home=None, ht_observed=True, cache_rows=[], **common) == "ht_observed"
    rows = [(captured - timedelta(days=2), [{"match_id": "3026756", "kickoff_time": future}]),
            (captured - timedelta(days=1), [{"match_id": "3026756", "kickoff_time": played}])]
    assert ev(actual_ft_home=None, ht_observed=False, cache_rows=rows, **common) == "source_kickoff_passed"
    # Listeden düşmüş (carried) eski kayıt kanıt sayılmaz; en son gerçek kayıt gelecekteyse kayıt yapılır
    rows = [(captured - timedelta(days=1), [{"match_id": "3026756", "kickoff_time": played, "carried": True}]),
            (captured - timedelta(days=2), [{"match_id": "3026756", "kickoff_time": future}])]
    assert ev(actual_ft_home=None, ht_observed=False, cache_rows=rows, **common) is None
    live = [(captured, [{"match_id": "3026756", "kickoff_time": future, "score_status": "live"}])]
    assert ev(actual_ft_home=None, ht_observed=False, cache_rows=live, **common) == "source_started"


@pytest.mark.asyncio
async def test_capture_skips_when_match_already_started(monkeypatch):
    monkeypatch.setattr(prematch_v4, "match_already_started", AsyncMock(return_value="source_kickoff_passed"))
    _empty_cond_table(monkeypatch)
    session = AsyncMock()
    picks, created = await prematch_v4.capture_v4_recommendations(
        session, match_id="1", analyzed_at=ANALYZED_AT, captured_at=NOW, kickoff_time=NOW + timedelta(hours=5),
        league_name="English Premier League", league_code="ENG PR", patterns={"pattern_ft_b": _pattern()},
    )
    assert (picks, created) == (None, False)
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_started_match_without_v5_snapshot_shows_frozen_v4(monkeypatch):
    """v5'ten önce dondurulup başlamış maç: o gün gösterilen v4 seçimi kaybolmaz."""
    v4_picks = [{"recommendation_id": "ft-display-v4:result:1", "market": "result"}]
    session = AsyncMock()
    session.get.side_effect = lambda _model, key: (
        MagicMock(picks=v4_picks) if key[1] == prematch_v4.V4_RULE_VERSION else None)
    session.execute.return_value = MagicMock(scalar_one_or_none=lambda: None)   # maç başlamış

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(services, "get_session", fake_session)
    row = Match(match_id="9", home_team="H", away_team="A", league_code="ENG PR",
                league_name="English Premier League", analyzed_at=ANALYZED_AT, kickoff_time=NOW)
    assert await services._frozen_recommendations(row, {}) == v4_picks


@pytest.mark.asyncio
async def test_capture_waits_until_48_hours_before_kickoff(monkeypatch):
    """Mayıs maçına Ekim'de sayfa ziyareti karar dondurmaz (ilk kayıt kazanır → maç günü kararı engellenirdi)."""
    _empty_cond_table(monkeypatch)
    session = AsyncMock()
    far = await prematch_v4.capture_v4_recommendations(
        session, match_id="1", analyzed_at=ANALYZED_AT, captured_at=NOW, kickoff_time=NOW + timedelta(days=204),
        league_name="English Premier League", league_code="ENG PR", patterns={"pattern_ft_b": _pattern()},
    )
    assert far == (None, False)
    session.execute.assert_not_awaited()
    assert prematch_v4._eligible(ANALYZED_AT, NOW, NOW + timedelta(hours=47), "English Premier League",
                                 "ENG PR", {"pattern_ft_b": _pattern()})
    assert not prematch_v4._eligible(ANALYZED_AT, NOW, NOW + timedelta(hours=49), "English Premier League",
                                     "ENG PR", {"pattern_ft_b": _pattern()})
