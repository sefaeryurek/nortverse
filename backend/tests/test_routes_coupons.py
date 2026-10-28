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

    monkeypatch.setattr(rc, "get_session", fake_session)
    monkeypatch.setattr(rc, "_match_state", fake_state)
    monkeypatch.setattr(rc, "_odds", no_odds)


def test_create_coupon_409_after_kickoff(monkeypatch):
    kickoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    match = SimpleNamespace(match_id="123", home_team="A", away_team="B", league_name="L", kickoff_time=kickoff)
    state = {"kickoff": kickoff, "actual_ft": False, "actual_ht": False, "started_reason": None,
             "board_status": None, "board_phase": None, "board_minute": None}
    _patch_db(monkeypatch, match, state)
    body = rc.CouponIn(legs=[rc.LegIn(match_id="123", period="ft", market="result", selection="1")])
    request = SimpleNamespace(state=SimpleNamespace(user=SimpleNamespace(id=1)))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(rc.create_coupon(body, request))
    assert exc.value.status_code == 409 and "Maç başladı" in exc.value.detail
