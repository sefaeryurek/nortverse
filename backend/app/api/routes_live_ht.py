"""Canlı İY → MS: devre arası ve 2. yarıdaki ana lig maçları + canlı model tahmini.

İY skoru: devre arasında anlık skor; 2. yarıda değişmez İY gözleminden (DB), yoksa panodan.
Tahmin: dondurulmuşsa defterden (`frozen`), değilse anlık hesaplanır (sadece görüntü).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Path, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select

from app.analysis.league_filter import canonical_league_name, is_main_league
from app.analysis.live_model import LIVE_RULE_VERSION, archive_ht_filtered, get_cond_table, predict_live
from app.api.live_ledger import match_phase, observed_ht
from app.api.live_snapshot import get_live_snapshot
from app.config import ISTANBUL_TZ
from app.db.connection import get_session
from app.db.models import FixtureCache, Match, MatchHtObservation, PredictionLedger
from app.scraper.fixture_scores import phase_from_minute

log = logging.getLogger(__name__)
router = APIRouter()


class LiveHTMatch(BaseModel):
    match_id: str
    home_team: str | None = None
    away_team: str | None = None
    ht_home: int
    ht_away: int
    live_home: int | None = None
    live_away: int | None = None
    live_minute: str | None = None
    phase: str | None = None
    league_name: str | None = None
    kickoff_time: str | None = None
    prediction: dict | None = None


def _is_second_half_or_later(minute: str | None, phase: str | None = None) -> bool:
    """Devre arası veya 2. yarı mı? Evre bilgisi varsa o esas; yoksa dakika (46+).

    45 ve 45+N hâlâ 1. yarı uzatmasıdır — İY skoru kesinleşmemiştir.
    """
    if phase in ("ht", "2h"):
        return True
    if phase == "1h":
        return False
    return phase_from_minute(minute) in ("ht", "2h")


async def _latest_ht_observations(session, ids: list[str]) -> dict[str, tuple[int, int]]:
    if not ids:
        return {}
    rows = (await session.execute(
        select(MatchHtObservation.match_id, MatchHtObservation.ht_home, MatchHtObservation.ht_away)
        .where(MatchHtObservation.match_id.in_(ids))
        .order_by(MatchHtObservation.id)
    )).all()
    return {r[0]: (r[1], r[2]) for r in rows}


async def _frozen_predictions(session, ids: list[str]) -> dict[str, dict]:
    """Defterdeki dondurulmuş canlı tahminler (MS satırının details'i tam tahmini taşır)."""
    if not ids:
        return {}
    rows = (await session.execute(
        select(PredictionLedger.match_id, PredictionLedger.details, PredictionLedger.recorded_at)
        .where(
            PredictionLedger.source == "live_ht",
            PredictionLedger.rule_version == LIVE_RULE_VERSION,
            PredictionLedger.market == "result",
            PredictionLedger.match_id.in_(ids),
        )
    )).all()
    return {
        r[0]: {**r[1], "frozen": True, "frozen_at": r[2].isoformat()}
        for r in rows if isinstance(r[1], dict)
    }


async def _fixture_cache_info(session, missing: list[str]) -> dict[str, tuple]:
    info: dict[str, tuple] = {}
    today = datetime.now(ISTANBUL_TZ).date()
    for day in (today, today - timedelta(days=1)):
        fc = (await session.execute(
            select(FixtureCache.matches_json).where(FixtureCache.date == day.isoformat())
        )).scalar_one_or_none()
        if not isinstance(fc, list):
            continue
        for raw in fc:
            mid = str(raw.get("match_id", ""))
            if mid in missing and mid not in info:
                info[mid] = (raw.get("home_team"), raw.get("away_team"),
                             raw.get("league_name") or raw.get("league_code"), None, None)
    return info


@router.get("/api/live-ht")
async def get_live_ht_matches() -> list[LiveHTMatch]:
    snap = await get_live_snapshot()
    if snap is None:
        return []

    live = {mid: fs for mid, fs in snap.scores.items()
            if fs.status == "live" and _is_second_half_or_later(fs.minute, fs.phase)}
    if not live:
        return []
    ids = list(live)

    async with get_session() as session:
        observations = await _latest_ht_observations(session, ids)
        db_rows = (await session.execute(select(Match).where(
            Match.match_id.in_(ids), Match.deleted_at.is_(None),
        ))).scalars().all()
        by_id = {m.match_id: m for m in db_rows}
        info = {m.match_id: (m.home_team, m.away_team, m.league_name, m.kickoff_time, m) for m in db_rows}
        missing = [mid for mid in ids if mid not in info]
        if missing:
            info.update(await _fixture_cache_info(session, missing))
        frozen = await _frozen_predictions(session, list(by_id))

    table = await get_cond_table()
    result: list[LiveHTMatch] = []
    for mid, fs in live.items():
        row = info.get(mid)
        if row is None:
            continue
        home, away, league, kickoff, match = row
        league = canonical_league_name(league) if league else None
        if not is_main_league(league):
            continue
        ht = observations.get(mid) or observed_ht(fs)
        if ht is None:
            continue
        prediction = frozen.get(mid)
        if prediction is None:
            blobs = [match.pattern_ft_b, match.pattern_ft_c, match.pattern_ft_d] if match else []
            prediction = {**predict_live(table, league, ht, blobs), "frozen": False, "frozen_at": None}
        result.append(LiveHTMatch(
            match_id=mid, home_team=home, away_team=away,
            ht_home=ht[0], ht_away=ht[1], live_home=fs.home, live_away=fs.away,
            live_minute=fs.minute, phase=match_phase(fs), league_name=league,
            kickoff_time=kickoff.isoformat() if kickoff else None,
            prediction=prediction,
        ))
    return result


@router.get("/api/live-ht/{match_id}/prediction")
async def get_live_prediction(
    match_id: str = Path(pattern=r"^[0-9]{1,12}$"),
    detail: bool = Query(False),
) -> dict:
    """Tek maçın canlı tahmini; detail=1 ile A1/A2/A3 İY-süzülmüş ikincil kartlar."""
    async with get_session() as session:
        match = (await session.execute(select(Match).where(
            Match.match_id == match_id, Match.deleted_at.is_(None),
        ))).scalar_one_or_none()
        if match is None:
            raise HTTPException(404, "Maç bulunamadı")
        frozen = (await _frozen_predictions(session, [match_id])).get(match_id)
        observation = (await _latest_ht_observations(session, [match_id])).get(match_id)

    if frozen is not None:
        prediction = frozen
        ht = (prediction["ht"]["home"], prediction["ht"]["away"])
    else:
        ht = observation
        if ht is None:
            snap = await get_live_snapshot()
            fs = snap.scores.get(match_id) if snap else None
            ht = observed_ht(fs) if fs else None
        if ht is None and match.actual_ht_home is not None:
            ht = (match.actual_ht_home, match.actual_ht_away)
        if ht is None:
            raise HTTPException(409, "İY skoru henüz bilinmiyor")
        table = await get_cond_table()
        prediction = {
            **predict_live(table, match.league_name or "", ht,
                           [match.pattern_ft_b, match.pattern_ft_c, match.pattern_ft_d]),
            "frozen": False, "frozen_at": None,
        }
    if detail:
        prediction = {**prediction, "archives": await archive_ht_filtered(
            {"b": match.pattern_ft_b, "c": match.pattern_ft_c, "d": match.pattern_ft_d}, ht,
        )}
    return prediction


# ─── WebSocket bağlantı yöneticisi (Sprint 82) ─────────────────────────────

_SEND_TIMEOUT = 5.0


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
        # Kopya üzerinde dön: gönderim sırasında bağlanan/kopan istemci kümeyi değiştirebilir.
        targets = list(self._connections)

        async def _send(ws: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(ws.send_text(data), timeout=_SEND_TIMEOUT)
                return None
            except Exception:
                return ws

        for dead in await asyncio.gather(*(_send(ws) for ws in targets)):
            if dead is not None:
                self._connections.discard(dead)

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
