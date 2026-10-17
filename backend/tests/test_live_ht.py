"""Canlı İY Eşleşme (routes_live_ht.py) birim testleri."""

from __future__ import annotations

import asyncio
import json

import pytest

from app.api.routes_live_ht import (
    LiveHTMatch,
    _ConnectionManager,
    _is_second_half_or_later,
)


class TestIsSecondHalfOrLater:
    def test_ht_string(self):
        assert _is_second_half_or_later("HT") is True

    def test_minute_45(self):
        assert _is_second_half_or_later("45") is False

    def test_minute_46(self):
        assert _is_second_half_or_later("46") is True

    def test_minute_55(self):
        assert _is_second_half_or_later("55") is True

    def test_minute_60(self):
        assert _is_second_half_or_later("60") is True

    def test_minute_75(self):
        assert _is_second_half_or_later("75") is True

    def test_minute_90(self):
        assert _is_second_half_or_later("90") is True

    def test_minute_90_plus(self):
        assert _is_second_half_or_later("90+3") is True

    def test_minute_45_plus(self):
        assert _is_second_half_or_later("45+2") is False

    def test_minute_46_plus(self):
        assert _is_second_half_or_later("46+1") is True

    def test_first_half(self):
        assert _is_second_half_or_later("30") is False

    def test_first_half_early(self):
        assert _is_second_half_or_later("1") is False

    def test_minute_44(self):
        assert _is_second_half_or_later("44") is False

    def test_none(self):
        assert _is_second_half_or_later(None) is False

    def test_empty(self):
        assert _is_second_half_or_later("") is False

    def test_non_numeric(self):
        assert _is_second_half_or_later("abc") is False

    def test_second_half_phase_without_minute(self):
        # "2nd Half" etiketi saat göstermeyebilir; maç listeden düşmemeli.
        assert _is_second_half_or_later(None, "2h") is True

    def test_ht_phase(self):
        assert _is_second_half_or_later(None, "ht") is True

    def test_first_half_phase_overrides_minute(self):
        assert _is_second_half_or_later("45+3", "1h") is False


class TestLiveHTMatchModel:
    def test_live_score_fields(self):
        m = LiveHTMatch(match_id="123", ht_home=1, ht_away=0, live_home=2, live_away=1)
        assert m.live_home == 2
        assert m.live_away == 1

    def test_live_score_defaults_none(self):
        m = LiveHTMatch(match_id="123", ht_home=1, ht_away=0)
        assert m.live_home is None
        assert m.live_away is None
        assert m.prediction is None


class _FakeWebSocket:
    """WebSocket davranışını taklit eden test double."""

    def __init__(self, *, fail_send: bool = False):
        self.accepted = False
        self.messages: list[str] = []
        self._fail_send = fail_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        if self._fail_send:
            raise RuntimeError("bağlantı koptu")
        self.messages.append(data)


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_connect_and_count(self):
        mgr = _ConnectionManager()
        ws = _FakeWebSocket()
        await mgr.connect(ws)
        assert mgr.count == 1
        assert ws.accepted

    @pytest.mark.asyncio
    async def test_disconnect(self):
        mgr = _ConnectionManager()
        ws = _FakeWebSocket()
        await mgr.connect(ws)
        mgr.disconnect(ws)
        assert mgr.count == 0

    @pytest.mark.asyncio
    async def test_disconnect_unknown_noop(self):
        mgr = _ConnectionManager()
        ws = _FakeWebSocket()
        mgr.disconnect(ws)
        assert mgr.count == 0

    @pytest.mark.asyncio
    async def test_broadcast(self):
        mgr = _ConnectionManager()
        ws1 = _FakeWebSocket()
        ws2 = _FakeWebSocket()
        await mgr.connect(ws1)
        await mgr.connect(ws2)
        await mgr.broadcast('{"test": true}')
        assert ws1.messages == ['{"test": true}']
        assert ws2.messages == ['{"test": true}']

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead(self):
        mgr = _ConnectionManager()
        ws_ok = _FakeWebSocket()
        ws_dead = _FakeWebSocket(fail_send=True)
        await mgr.connect(ws_ok)
        await mgr.connect(ws_dead)
        assert mgr.count == 2
        await mgr.broadcast("data")
        assert mgr.count == 1
        assert ws_ok.messages == ["data"]

    @pytest.mark.asyncio
    async def test_broadcast_empty_no_error(self):
        mgr = _ConnectionManager()
        await mgr.broadcast("test")

    @pytest.mark.asyncio
    async def test_broadcast_survives_connect_during_send(self):
        mgr = _ConnectionManager()
        late = _FakeWebSocket()

        class _Slow(_FakeWebSocket):
            async def send_text(self, data: str) -> None:
                await mgr.connect(late)  # gönderim sırasında yeni bağlantı
                await super().send_text(data)

        slow = _Slow()
        await mgr.connect(slow)
        await mgr.broadcast("x")
        assert slow.messages == ["x"]
        assert mgr.count == 2

    @pytest.mark.asyncio
    async def test_broadcast_drops_hanging_client(self, monkeypatch):
        import app.api.routes_live_ht as mod
        monkeypatch.setattr(mod, "_SEND_TIMEOUT", 0.01)
        mgr = _ConnectionManager()

        class _Hang(_FakeWebSocket):
            async def send_text(self, data: str) -> None:
                await asyncio.sleep(1)

        ok, hang = _FakeWebSocket(), _Hang()
        await mgr.connect(ok)
        await mgr.connect(hang)
        await mgr.broadcast("y")
        assert ok.messages == ["y"]
        assert mgr.count == 1

    @pytest.mark.asyncio
    async def test_multiple_broadcasts(self):
        mgr = _ConnectionManager()
        ws = _FakeWebSocket()
        await mgr.connect(ws)
        await mgr.broadcast("msg1")
        await mgr.broadcast("msg2")
        assert ws.messages == ["msg1", "msg2"]
