"""Kupondaş kapanış kuralı (Sprint 94 A1/A2 — K2: kupon sadece maç öncesi)."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import routes_coupons as rc

KICK = datetime(2026, 10, 27, 17, 0, tzinfo=timezone.utc)


def _reason(period, now, **kw):
    base = {"kickoff": KICK, "actual_ft": False, "actual_ht": False}
    return rc.closed_reason(period=period, now=now, **{**base, **kw})


def test_open_before_kickoff():
    assert _reason("ft", KICK - timedelta(minutes=10)) is None
    assert _reason("ht", KICK - timedelta(minutes=10)) is None


def test_closed_reason_ft_when_actual_score_present():
    assert _reason("ft", KICK - timedelta(hours=1), actual_ft=True) == "Maç bitti"


def test_closed_reason_ht_when_board_2h_and_state_zero():
    # Oran ucunun durum alanı hep 0; pano 2. yarı diyorsa İY kapalı (başlama saati yer tutucu olsa bile)
    assert _reason("ht", KICK - timedelta(hours=2), board_status="live", board_phase="2h") == "İlk yarı bitti"


def test_closed_reason_ht_minute_with_stoppage_45plus2():
    assert rc.minute_value("45+2") == (45, 2)
    assert rc.minute_value("HT") is None
    assert _reason("ht", KICK - timedelta(hours=2), odds={"live": {"minute": "45+2"}}) == "İlk yarı bitti"
    assert _reason("ht", KICK - timedelta(hours=2), board_minute="HT") == "İlk yarı bitti"


def test_closed_reason_time_limits_without_board():
    assert _reason("ht", KICK + timedelta(minutes=47)) == "İlk yarı bitti"
    assert _reason("ft", KICK + timedelta(minutes=115)) == "Maç bitti"


def test_prematch_only_closes_started_match():
    assert _reason("ft", KICK + timedelta(minutes=1)).startswith("Maç başladı")
    # DB saati yer tutucu (henüz gelecekte) ama maç içi oran satırı / bülten maçın başladığını söylüyor
    assert _reason("ft", KICK - timedelta(hours=1), odds={"started": True}).startswith("Maç başladı")
    assert _reason("ft", KICK - timedelta(hours=1), started_reason="source_started").startswith("Maç başladı")
    assert _reason("ft", KICK - timedelta(hours=1), board_status="live").startswith("Maç başladı")


def test_postponed_and_ht_observation():
    assert _reason("ft", KICK - timedelta(hours=1), board_status="postponed") == "Maç ertelendi / iptal"
    assert _reason("ht", KICK - timedelta(hours=1), started_reason="ht_observed") == "İlk yarı bitti"
    assert _reason("ft", KICK - timedelta(hours=1), started_reason="result_known") == "Maç bitti"


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


def _patch_db(monkeypatch, match, state):
    class _Session:
        async def execute(self, *_a, **_k):
            return _Result([match])

    @asynccontextmanager
    async def fake_session():
        yield _Session()

    async def fake_state(_session, _match, _now):
        return state

    async def no_odds(*_a, **_k):
        raise AssertionError("başlamış maç için kaynağa gidilmemeli")

    async def fake_refs(_session, ids, _now):
        return {match.match_id: match} if match.match_id in ids else {}

    monkeypatch.setattr(rc, "get_session", fake_session)
    monkeypatch.setattr(rc, "_open_refs", fake_refs)
    monkeypatch.setattr(rc, "_match_state", fake_state)
    monkeypatch.setattr(rc, "_odds", no_odds)


def test_create_coupon_409_after_kickoff(monkeypatch):
    kickoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    match = SimpleNamespace(match_id="123", home_team="A", away_team="B", league_name="L", kickoff_time=kickoff,
                            source="fixture")
    state = {"kickoff": kickoff, "actual_ft": False, "actual_ht": False, "started_reason": None,
             "board_status": None, "board_phase": None, "board_minute": None}
    _patch_db(monkeypatch, match, state)
    body = rc.CouponIn(legs=[rc.LegIn(match_id="123", period="ft", market="result", selection="1")])
    request = SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(id=1)), headers={})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(rc.create_coupon(body, request))
    assert exc.value.status_code == 409 and "Maç başladı" in exc.value.detail



# ─── Sprint 94 J2 / J3 / J4 ───────────────────────────────────────────────────────────────────────

def _open_state(kickoff):
    return {"kickoff": kickoff, "actual_ft": False, "actual_ht": False, "started_reason": None,
            "board_status": None, "board_phase": None, "board_minute": None}


def _request(user_id=1, key=None):
    headers = {"idempotency-key": key} if key else {}
    return SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(id=user_id)), headers=headers)


def _patch_prematch(monkeypatch, odds):
    kickoff = datetime.now(timezone.utc) + timedelta(hours=3)
    match = SimpleNamespace(match_id="123", home_team="A", away_team="B", league_name="L", kickoff_time=kickoff,
                            source="fixture")
    added: list = []

    class _Session:
        async def execute(self, *_a, **_k):
            return _Result([match])

        def add(self, obj):
            added.append(obj)

        async def flush(self):
            for obj in added:
                if obj.__class__.__name__ == "Coupon":
                    obj.id = 77

    @asynccontextmanager
    async def fake_session():
        yield _Session()

    async def fake_state(_session, _match, _now):
        return _open_state(kickoff)

    calls = []

    async def fake_odds(match_id, *, max_age):
        calls.append(match_id)
        return odds

    async def fake_refs(_session, ids, _now):
        return {match.match_id: match} if match.match_id in ids else {}

    monkeypatch.setattr(rc, "get_session", fake_session)
    monkeypatch.setattr(rc, "_open_refs", fake_refs)
    monkeypatch.setattr(rc, "_match_state", fake_state)
    monkeypatch.setattr(rc, "_odds", fake_odds)
    rc._idempotency.clear()
    return calls


ODDS = {"started": False, "live": None, "ft": {"result": {"1": 2.0, "X": 3.2, "2": 3.6},
                                               "ou": {"line": 2.5, "over": 1.9, "under": 1.9}}, "ht": {}}


def test_one_leg_per_match(monkeypatch):
    _patch_prematch(monkeypatch, ODDS)
    body = rc.CouponIn(legs=[rc.LegIn(match_id="123", period="ft", market="result", selection="1"),
                             rc.LegIn(match_id="123", period="ft", market="ou", selection="over")])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(rc.create_coupon(body, _request()))
    assert exc.value.status_code == 400


def test_max_legs_is_ten():
    assert rc.MAX_LEGS == 10


def test_odds_worse_than_seen_needs_confirmation(monkeypatch):
    _patch_prematch(monkeypatch, ODDS)
    body = rc.CouponIn(legs=[rc.LegIn(match_id="123", period="ft", market="result", selection="1", seen_odds=2.2)])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(rc.create_coupon(body, _request()))
    assert exc.value.status_code == 409 and exc.value.detail["code"] == "odds_changed"
    assert exc.value.detail["changes"][0]["new_odds"] == 2.0


def test_line_change_needs_confirmation_and_small_drift_is_accepted(monkeypatch):
    _patch_prematch(monkeypatch, ODDS)
    moved = rc.CouponIn(legs=[rc.LegIn(match_id="123", period="ft", market="ou", selection="over", line=2.75)])
    with pytest.raises(HTTPException):
        asyncio.run(rc.create_coupon(moved, _request()))
    ok = rc.CouponIn(legs=[rc.LegIn(match_id="123", period="ft", market="result", selection="1", seen_odds=2.04)])
    out = asyncio.run(rc.create_coupon(ok, _request()))
    assert out["id"] == 77 and out["legs"][0]["odds"] == 2.0


def test_idempotency_key_returns_first_response(monkeypatch):
    calls = _patch_prematch(monkeypatch, ODDS)
    body = rc.CouponIn(legs=[rc.LegIn(match_id="123", period="ft", market="result", selection="1")])
    first = asyncio.run(rc.create_coupon(body, _request(key="abc")))
    second = asyncio.run(rc.create_coupon(body, _request(key="abc")))
    assert first == second and len(calls) == 1


def test_saved_leg_keeps_match_source(monkeypatch):
    """Sprint 94 J6: bülten tabanlı maçın bacağı `source='fixture'` ile yazılır."""
    _patch_prematch(monkeypatch, ODDS)
    added = []
    real_leg = rc.CouponLeg

    def capture(**kw):
        leg = real_leg(**kw)
        added.append(leg)
        return leg

    monkeypatch.setattr(rc, "CouponLeg", capture)
    body = rc.CouponIn(legs=[rc.LegIn(match_id="123", period="ft", market="result", selection="1")])
    asyncio.run(rc.create_coupon(body, _request()))
    assert added[0].source == "fixture"


def test_match_state_uses_fixture_postponed_status(monkeypatch):
    from app.analysis import prematch_v4
    from app.analysis.match_ref import MatchRef
    from app.api import live_snapshot

    async def not_started(*_a):
        return None

    async def no_board():
        return None

    monkeypatch.setattr(prematch_v4, "match_already_started", not_started)
    monkeypatch.setattr(live_snapshot, "get_live_snapshot", no_board)
    ref = MatchRef(match_id="9", home_team="A", away_team="B", league_name=None, source="fixture",
                   kickoff_time=KICK, status="postponed")
    state = asyncio.run(rc._match_state(None, ref, KICK - timedelta(hours=2)))
    assert state["board_status"] == "postponed"
    assert rc.closed_reason(period="ft", now=KICK - timedelta(hours=2), **state) == "Maç ertelendi / iptal"
