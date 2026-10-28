"""İY oran panosu ucu (Sprint 94 M3): oransız maç gizlenir, en güçlü seçenek öne, model notu sadece İY 1/X/2."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api import routes_ht

KICK = datetime(2026, 10, 28, 17, 0, tzinfo=timezone.utc)


FUTURE = datetime.now(timezone.utc) + timedelta(days=1)


def _row(mid, ht=None, kickoff=KICK):
    return SimpleNamespace(match_id=mid, home_team=f"H{mid}", away_team=f"A{mid}", league_name="English Premier League",
                           league_code="ENG PR", kickoff_time=kickoff,
                           actual_ht_home=None if ht is None else ht[0], actual_ht_away=None if ht is None else ht[1])


@pytest.fixture
def board(monkeypatch):
    rows = [_row("1", kickoff=FUTURE), _row("2"), _row("3", ht=(1, 0))]
    session = AsyncMock()
    session.execute.side_effect = [MagicMock(all=lambda: rows),
                                   MagicMock(scalars=lambda: MagicMock(all=lambda: []))]

    @asynccontextmanager
    async def fake_session():
        yield session

    odds = {
        "1": {"op": {"1": 2.6, "X": 2.0, "2": 4.6}},                                 # en güçlü: X ~%46
        "2": {},                                                                    # İY oranı açılmamış → gizli
        "3": {"op": {"1": 1.8, "X": 2.3, "2": 6.0}, "ou": {"line": 1.0, "over": 1.95, "under": 1.85}},
    }
    monkeypatch.setattr(routes_ht, "get_session", fake_session)
    monkeypatch.setattr(routes_ht, "get_poisson_model", AsyncMock(return_value=None))
    monkeypatch.setattr(routes_ht, "_odds_by_match", AsyncMock(return_value=(odds, {}, set())))
    monkeypatch.setattr(routes_ht, "match_ht", lambda *_a: {"probs": {"result": {"1": 40.0, "X": 45.0, "2": 15.0},
                                                                      "lambda": {"home": 0.7, "away": 0.4}}})
    return rows


@pytest.mark.asyncio
async def test_hides_matches_without_odds_and_orders_by_strongest(board):
    out = await routes_ht.ht_strategy(target_date="2026-10-28", shadow=False)
    ids = [m["match_id"] for m in out["matches"]]
    assert "2" not in ids                                # oran yok → listede yok
    assert ids == ["3", "1"]                             # en güçlü seçenek (3: ev ~%50) önde
    for m in out["matches"]:
        pcts = [o["pct"] for o in m["options"]]
        assert pcts == sorted(pcts, reverse=True)        # maç içinde de güçlüden zayıfa


@pytest.mark.asyncio
async def test_model_note_only_on_result_market_and_outcome_for_finished(board):
    out = await routes_ht.ht_strategy(target_date="2026-10-28", shadow=False)
    upcoming = next(m for m in out["matches"] if m["match_id"] == "1")
    for o in upcoming["options"]:
        assert (o["model_pct"] is None) == (o["market"] == "ou")
    assert upcoming["expected_goals"] == {"home": 0.7, "away": 0.4}
    finished = next(m for m in out["matches"] if m["match_id"] == "3")
    assert finished["final_ht"] == "1-0"
    for o in finished["options"]:
        assert o["outcome"] in ("hit", "miss", "push", "half")
        # Sprint 94 K-4: dondurulmuş kayıt yok → güncel model sonucu görmüş olabilir, gösterilmez
        assert o["model_pct"] is None
    home = next(o for o in finished["options"] if o["market"] == "result" and o["selection"] == "1")
    assert home["outcome"] == "hit"
    assert finished["expected_goals"] is None


@pytest.mark.asyncio
async def test_bad_date_is_400():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        await routes_ht.ht_strategy(target_date="28-10-2026", shadow=False)
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_refresh_shared_for_same_match_and_fetch_outside_session(monkeypatch):
    """Sprint 94 K-1: aynı maça eşzamanlı istekler tek çekimi paylaşır (eskiden ikincisi None alıp maç düşüyordu);
    kaynak beklenirken DB oturumu açık değil."""
    from app.scraper import odds as odds_mod

    calls, session_open = [], []

    async def slow_fetch(match_id, half):
        calls.append(match_id)
        session_open.append(bool(opened))
        await asyncio.sleep(0.05)
        return {"op": [{"mt": 1}]}

    opened = []

    @asynccontextmanager
    async def fake_session():
        opened.append(1)
        try:
            yield "oturum"
        finally:
            opened.pop()

    async def store(session, match_id, scope, history, now, current=None):
        assert session == "oturum" and scope == "ht"
        return history

    monkeypatch.setattr(odds_mod, "fetch_odds", slow_fetch)
    monkeypatch.setattr(odds_mod, "store_history", store)
    monkeypatch.setattr(routes_ht, "get_session", fake_session)
    results = await asyncio.gather(*(routes_ht._refresh("9") for _ in range(4)))
    assert calls == ["9"] and session_open == [False]
    assert results == [{"op": [{"mt": 1}]}] * 4      # hepsi aynı sonucu alır
    assert routes_ht._inflight == {}
    await routes_ht._refresh("9")                    # bittikten sonra yeniden çekilebilir
    assert calls == ["9", "9"]


@pytest.mark.asyncio
async def test_pending_odds_shown_as_placeholder(monkeypatch, board):
    monkeypatch.setattr(routes_ht, "_odds_by_match",
                        AsyncMock(return_value=({"1": {"op": {"1": 2.6, "X": 2.0, "2": 4.6}}}, {}, {"2"})))
    out = await routes_ht.ht_strategy(target_date="2026-10-28", shadow=False)
    pending = next(m for m in out["matches"] if m["match_id"] == "2")
    assert pending["odds_pending"] is True and pending["options"] == []
    assert out["matches"][0]["match_id"] == "1"      # oranı olan önde


def test_stale_odds_refreshed_but_finished_closing_kept(monkeypatch):
    spawned = []
    now = datetime.now(timezone.utc)
    rows = [_row("1"), _row("2", ht=(0, 0))]
    rows[0].kickoff_time = now + timedelta(hours=2)
    rows[1].kickoff_time = now - timedelta(hours=3)
    stored = {"1": (now - timedelta(hours=1), {}), "2": (now - timedelta(hours=1), {})}  # ikisi de 15 dk'dan eski
    monkeypatch.setattr(routes_ht, "_stored_odds", AsyncMock(return_value=stored))
    monkeypatch.setattr(routes_ht, "_spawn", lambda mid: spawned.append(mid))
    _odds, _hist, pending = asyncio.run(routes_ht._odds_by_match(rows))
    assert spawned == ["1"]  # biten maçın kapanış oranı yeterli, kaynağa gidilmez
    assert pending == set()


@pytest.mark.asyncio
async def test_prefetch_only_main_league_missing_or_stale(monkeypatch):
    """Sprint 94 I2: yaklaşan ana lig maçlarından İY oranı olmayan / 15 dk'dan eski olanlar önceden çekilir."""
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    rows = [SimpleNamespace(match_id=mid, league_name=league, league_code=None)
            for mid, league in (("fresh", "English Premier League"), ("stale", "English Premier League"),
                                ("missing", "Spanish La Liga"), ("cup", "UEFA Champions League"))]
    session = AsyncMock()
    session.execute.return_value = MagicMock(all=lambda: rows)

    @asynccontextmanager
    async def fake_session():
        yield session

    stored = {"fresh": (now - timedelta(minutes=5), {}), "stale": (now - timedelta(minutes=40), {})}
    fetched = []

    async def fake_refresh(mid):
        fetched.append(mid)

    monkeypatch.setattr(routes_ht, "get_session", fake_session)
    monkeypatch.setattr(routes_ht, "_stored_odds", AsyncMock(return_value=stored))
    monkeypatch.setattr(routes_ht, "_refresh", fake_refresh)
    assert await routes_ht.prefetch_upcoming(now) == 2
    assert fetched == ["stale", "missing"]  # taze olan ve ana lig dışı çekilmez
