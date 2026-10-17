"""Canlı İY Eşleşme — devre arası ve 2. yarı maçları için arşiv istatistikleri.

Sprint 47+52: Devre arasında İY skoru yakalanan maçlar, maç bitene kadar
bu listede kalır. Hem İY skoru hem güncel canlı skor gösterilir.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select

from app.config import ISTANBUL_TZ
from app.analysis.league_filter import is_main_league
from app.api.live_snapshot import get_live_snapshot
from app.db.connection import get_session
from app.db.models import FixtureCache, Match

log = logging.getLogger(__name__)
router = APIRouter()

_ht_observed: dict[str, tuple[int, int]] = {}
_ht_observed_day: str = ""



class LiveHTMatch(BaseModel):
    match_id: str
    home_team: str | None = None
    away_team: str | None = None
    ht_home: int
    ht_away: int
    live_home: int | None = None
    live_away: int | None = None
    live_minute: str | None = None
    league_name: str | None = None
    kickoff_time: str | None = None




def _is_second_half_or_later(minute: str | None) -> bool:
    """HT veya 2. yarı (46+) dakikası mı?

    45 ve 45+N hâlâ 1. yarı uzatmasıdır — İY skoru kesinleşmemiştir.
    Sadece "HT" (devre arası) veya 46+ dakikalar True döner.
    """
    if not minute:
        return False
    if minute == "HT":
        return True
    try:
        base = int(minute.split("+")[0])
        return base >= 46
    except (ValueError, IndexError):
        return False


def _cleanup_observed() -> None:
    global _ht_observed_day
    today = datetime.now(ISTANBUL_TZ).strftime("%Y-%m-%d")
    if _ht_observed_day != today:
        _ht_observed.clear()
        _ht_observed_day = today


@router.get("/api/live-ht")
async def get_live_ht_matches() -> list[LiveHTMatch]:
    _cleanup_observed()
    snap = await get_live_snapshot()
    if snap is None:
        return []

    result: list[LiveHTMatch] = []
    for mid, fs in snap.scores.items():
        if fs.status == "finished":
            _ht_observed.pop(mid, None)
            continue

        if fs.minute == "HT" and fs.home is not None and fs.away is not None:
            _ht_observed[mid] = (fs.home, fs.away)
            result.append(LiveHTMatch(
                match_id=mid,
                ht_home=fs.home,
                ht_away=fs.away,
                live_home=fs.home,
                live_away=fs.away,
                live_minute=fs.minute,
            ))
        elif _is_second_half_or_later(fs.minute):
            ht_h: int | None = None
            ht_a: int | None = None
            if mid in _ht_observed:
                ht_h, ht_a = _ht_observed[mid]
            elif fs.ht_home is not None and fs.ht_away is not None:
                ht_h, ht_a = fs.ht_home, fs.ht_away
                _ht_observed[mid] = (ht_h, ht_a)
            if ht_h is not None and ht_a is not None:
                result.append(LiveHTMatch(
                    match_id=mid,
                    ht_home=ht_h,
                    ht_away=ht_a,
                    live_home=fs.home,
                    live_away=fs.away,
                    live_minute=fs.minute,
                ))

    if result:
        ids = [m.match_id for m in result]
        async with get_session() as session:
            stmt = select(
                Match.match_id, Match.home_team, Match.away_team,
                Match.league_name, Match.kickoff_time,
            ).where(Match.match_id.in_(ids), Match.deleted_at.is_(None))
            rows = (await session.execute(stmt)).all()
            info: dict[str, tuple] = {r[0]: r for r in rows}

            missing_ids = [mid for mid in ids if mid not in info]
            if missing_ids:
                today = datetime.now(ISTANBUL_TZ).strftime("%Y-%m-%d")
                for date_str in (today,):
                    fc = (await session.execute(
                        select(FixtureCache.matches_json).where(FixtureCache.date == date_str)
                    )).scalar_one_or_none()
                    if fc and isinstance(fc, list):
                        for raw in fc:
                            mid = str(raw.get("match_id", ""))
                            if mid in missing_ids and mid not in info:
                                info[mid] = (
                                    mid,
                                    raw.get("home_team"),
                                    raw.get("away_team"),
                                    raw.get("league_name"),
                                    None,
                                )

        enriched: list[LiveHTMatch] = []
        for m in result:
            r = info.get(m.match_id)
            if not r:
                continue
            league = r[3]
            if not is_main_league(league):
                continue
            m.home_team = r[1]
            m.away_team = r[2]
            m.league_name = league
            m.kickoff_time = r[4].isoformat() if r[4] else None
            enriched.append(m)
        result = enriched
    return result




# ─── WebSocket bağlantı yöneticisi (Sprint 82) ─────────────────────────────

class _ConnectionManager:
    """Bağlı WebSocket istemcilerini takip eder ve toplu mesaj gönderir."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        log.info("WebSocket bağlantısı açıldı — toplam: %d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        log.info("WebSocket bağlantısı kapandı — toplam: %d", len(self._connections))

    async def broadcast(self, data: str) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    @property
    def count(self) -> int:
        return len(self._connections)


_ws_manager = _ConnectionManager()
_WS_BROADCAST_INTERVAL = 15.0
_ws_broadcaster_task: asyncio.Task | None = None


async def _ws_broadcaster() -> None:
    """Periyodik olarak canlı maç verisi çekip tüm bağlı istemcilere gönderir."""
    while True:
        try:
            await asyncio.sleep(_WS_BROADCAST_INTERVAL)
            if _ws_manager.count == 0:
                continue
            matches = await get_live_ht_matches()
            payload = json.dumps(
                [m.model_dump() for m in matches],
                ensure_ascii=False,
            )
            await _ws_manager.broadcast(payload)
        except asyncio.CancelledError:
            break
        except Exception:
            log.warning("WebSocket broadcast hatası", exc_info=True)


def start_ws_broadcaster() -> None:
    global _ws_broadcaster_task
    if _ws_broadcaster_task is None or _ws_broadcaster_task.done():
        _ws_broadcaster_task = asyncio.create_task(_ws_broadcaster())
        log.info("WebSocket broadcaster başlatıldı (interval=%.0fs)", _WS_BROADCAST_INTERVAL)


async def stop_ws_broadcaster() -> None:
    global _ws_broadcaster_task
    if _ws_broadcaster_task and not _ws_broadcaster_task.done():
        _ws_broadcaster_task.cancel()
        try:
            await _ws_broadcaster_task
        except asyncio.CancelledError:
            pass
        _ws_broadcaster_task = None
        log.info("WebSocket broadcaster durduruldu")


@router.websocket("/ws/live-ht")
async def ws_live_ht(ws: WebSocket) -> None:
    """Canlı maç verisi WebSocket endpoint'i.

    Bağlantı açılır açılmaz mevcut veriyi gönderir,
    sonra broadcaster periyodik güncelleme yapar.
    İstemci "ping" gönderirse "pong" döner.
    """
    await _ws_manager.connect(ws)
    try:
        matches = await get_live_ht_matches()
        initial = json.dumps(
            [m.model_dump() for m in matches],
            ensure_ascii=False,
        )
        await ws.send_text(initial)

        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=60.0)
                if msg == "ping":
                    await ws.send_text("pong")
            except asyncio.TimeoutError:
                await ws.send_text("pong")
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        log.warning("WebSocket hata", exc_info=True)
    finally:
        _ws_manager.disconnect(ws)
