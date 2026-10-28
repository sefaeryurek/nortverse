"""Canlı İY: devre arası ve 2. yarıdaki ana lig maçları + arşiv görünümü (live-arch-v1).

İY skoru: devre arasında anlık skor; 2. yarıda değişmez İY gözleminden (DB), yoksa panodan.
Görünüm: A1/A2/A3 + Genel pazar oranları; öne çıkanlar (%85+) maç kaydedildiyse defterden gelir
(ekranda görülen = değerlendirilen). Eski COND modeli ekranda yok, sadece kaydedilip ölçülür.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Path, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import exists, func, select

from app.analysis.league_filter import canonical_league_name, is_shadow_league, is_tracked_league
from app.analysis import live_archive, live_poisson
from app.analysis.live_model import LIVE_RULE_VERSION, get_cond_table
from app.api.live_ledger import match_phase, observed_ht
from app.api.live_snapshot import get_live_snapshot
from app.db.connection import get_session
from app.analysis.ledger import INVALIDATED_VERSION
from app.db.models import (
    Match, MatchHtObservation, PredictionLedger, PredictionResolution,
)
from app.scraper.fixture_scores import phase_from_minute

log = logging.getLogger(__name__)
router = APIRouter()


def _valuable(details: dict) -> bool:
    """Sprint 94 H3: karar İY skorundan zaten belli mi? Defterdeki işaret; eski kayıtta COND oranından."""
    if "valuable" in details:
        return bool(details["valuable"])
    cond = details.get("cond_pct")
    return cond is None or cond < live_poisson.VALUABLE_COND_BELOW


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
    frozen: bool = False
    frozen_at: str | None = None
    archive_view: dict | None = None
    # Ekrandaki ana canlı kararlar (live-poisson-v1.1, Sprint 93)
    decisions: list[dict] = []
    # Gölgedeki lig (Sprint 92): ekran varsayılan olarak gizler, "gölge ligleri göster" açıkken "Deneme" etiketiyle
    shadow: bool = False


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


async def _frozen_info(session, ids: list[str]) -> dict[str, dict]:
    """Kaydedilmiş maçlar: kayıt anı + defterdeki %85+ arşiv işaretleri (görünen = değerlendirilen)."""
    if not ids:
        return {}
    rows = (await session.execute(
        select(PredictionLedger.match_id, PredictionLedger.rule_version, PredictionLedger.recorded_at,
               PredictionLedger.period, PredictionLedger.market, PredictionLedger.selection,
               PredictionLedger.archive, PredictionLedger.prob_shown_bp, PredictionLedger.sample_n,
               PredictionLedger.details)
        .where(
            PredictionLedger.source == "live_ht",
            PredictionLedger.rule_version.in_([LIVE_RULE_VERSION, *live_archive.LIVE_ARCHIVE_RULE_VERSIONS,
                                               *live_poisson.LIVE_POISSON_RULE_VERSIONS]),
            PredictionLedger.match_id.in_(ids),
            # Hatalı veriyle üretilip geçersiz sayılan kayıtlar ekranda "kayıt" gibi gösterilmez.
            ~exists().where(
                PredictionResolution.ledger_id == PredictionLedger.id,
                PredictionResolution.resolver_version == INVALIDATED_VERSION,
            ),
        )
        .order_by(PredictionLedger.id)
    )).all()
    out: dict[str, dict] = {}
    for r in rows:
        entry = out.setdefault(r.match_id, {"frozen_at": r.recorded_at.isoformat(), "highlights": [], "archived": False})
        if r.rule_version == LIVE_RULE_VERSION and r.market == "result":
            entry["archived"] = (r.details or {}).get("archive_rule_version") in live_archive.LIVE_ARCHIVE_RULE_VERSIONS
        details = r.details or {}
        if r.rule_version in live_poisson.LIVE_POISSON_RULE_VERSIONS:
            # Takım gücü modeli kararları (v1.1'den beri ekrandaki ana karar)
            entry.setdefault("poisson", []).append({
                "period": r.period, "market": r.market, "selection": r.selection, "pct": r.prob_shown_bp / 100,
                "cond_pct": details.get("cond_pct"), "cond_n": details.get("cond_n"),
                "best": bool(details.get("best")), "rule_version": r.rule_version,
                "valuable": _valuable(details),
            })
            continue
        if r.rule_version not in live_archive.LIVE_ARCHIVE_RULE_VERSIONS:
            continue
        entry["archived"] = True
        entry["highlights"].append({
            "period": r.period, "market": r.market, "selection": r.selection,
            "pct": r.prob_shown_bp / 100, "archive": r.archive or live_archive.GENERAL,
            "label": details.get("label") or (r.archive or "genel").upper(),
            "n": r.sample_n or 0, "risky": bool(details.get("risky")),
            # v1 kayıtlarında `sources` yok → ekran eski (arşiv başına) düzenini kullanır
            "sources": details.get("sources"),
            "archive_pct": details.get("archive_pct"), "cond_n": details.get("cond_n"),
            "cond_level": details.get("cond_level"),
            "conflict": bool(details.get("conflict")), "rule_version": r.rule_version,
        })
    # İzleyicinin değerlendirdiği ama karar çıkmayan maçlar da "kayıtlı" sayılır: ekranda kararlar sonradan
    # (biten maçın güncel modeliyle) yeniden hesaplanmaz, boş liste gösterilir (Sprint 94 B4).
    evaluated = (await session.execute(
        select(MatchHtObservation.match_id, func.min(MatchHtObservation.observed_at))
        .where(MatchHtObservation.source == "livescore", MatchHtObservation.match_id.in_(ids))
        .group_by(MatchHtObservation.match_id)
    )).all()
    for match_id, observed_at in evaluated:
        entry = out.setdefault(match_id, {"frozen_at": observed_at.isoformat(), "highlights": [], "archived": True})
        entry["archived"] = True
        entry.setdefault("poisson", [])
    for entry in out.values():
        entry["highlights"].sort(key=lambda h: (h["risky"], -h["pct"], -h["n"]))
    return out


async def _poisson_decisions(match: Match, ht: tuple[int, int], frozen: dict | None, view: dict | None) -> list[dict]:
    """Ekrandaki ana canlı kararlar (live-poisson-v1.1). Kaydedildiyse defterden, değilse anlık hesap.

    `confirmed`: arşiv + lig geçmişi kuralı (live-arch-v2) aynı seçimi yaptı mı (geçmişte ikisinin uyuştuğu
    kararlar %93,5 tuttu). `historical`: aynı pazarda geçmiş isabet (backtest).
    """
    if frozen and frozen.get("poisson") is not None:
        picks = frozen["poisson"]
    else:
        try:
            league = match.league_name or ""
            prediction = live_poisson.predict(await live_poisson.get_poisson_model(), league,
                                              match.home_team, match.away_team, ht)
            picks = [{
                "period": p["period"], "market": p["market"], "selection": p["selection"], "pct": p["pct"],
                "cond_pct": p["cond_pct"], "cond_n": p["cond_n"], "best": p["best"],
                "rule_version": live_poisson.LIVE_POISSON_RULE_VERSION, "valuable": p["valuable"],
            } for p in live_poisson.decisions(prediction, live_poisson.cond_lookup(await get_cond_table(), league, ht))]
        except Exception:
            log.warning("Canlı Poisson kararları hesaplanamadı [%s]", match.match_id, exc_info=True)
            picks = []
    confirmed = {(h["period"], h["market"], h["selection"]) for h in (view or {}).get("highlights", [])
                 if h.get("sources")}
    try:
        table = await live_poisson.load_hit_table()
    except Exception:
        table = {}
    return sorted(({**p, "confirmed": (p["period"], p["market"], p["selection"]) in confirmed,
                    "historical": table.get((p["period"], p["market"]))} for p in picks),
                  key=lambda p: -p["pct"])


async def _view_for(match: Match, ht: tuple[int, int], frozen: dict | None, *, with_matches: bool = False) -> dict:
    blobs = {"b": match.pattern_ft_b, "c": match.pattern_ft_c, "d": match.pattern_ft_d}
    view = await live_archive.load_view(match.match_id, blobs, ht, league=match.league_name or "",
                                        with_matches=with_matches)
    if frozen and frozen.get("archived"):
        try:
            table = await live_archive.load_hit_table()
        except Exception:
            table = {}
        versions = {h.get("rule_version") for h in frozen["highlights"]}
        rule_version = (live_archive.LIVE_ARCHIVE_RULE_VERSION
                        if live_archive.LIVE_ARCHIVE_RULE_VERSION in versions or not versions
                        else max(versions))
        view = {**view, "rule_version": rule_version,
                "highlights": live_archive.annotate(frozen["highlights"], table)}
    return view


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
        # Bülten gibi: sadece analiz edilmiş maçlar (kural dışı / analizsiz maçta gösterilecek veri yok).
        db_rows = (await session.execute(select(Match).where(
            Match.match_id.in_(ids), Match.deleted_at.is_(None), Match.ft_scores_1.isnot(None),
        ))).scalars().all()
        by_id = {m.match_id: m for m in db_rows}
        frozen = await _frozen_info(session, list(by_id))

    result: list[LiveHTMatch] = []
    for mid, fs in live.items():
        match = by_id.get(mid)
        if match is None:
            continue
        home, away, kickoff = match.home_team, match.away_team, match.kickoff_time
        league = canonical_league_name(match.league_name) if match.league_name else None
        if not is_tracked_league(league):
            continue
        ht = observations.get(mid) or observed_ht(fs)
        if ht is None:
            continue
        record = frozen.get(mid)
        view = await _view_for(match, ht, record)
        decisions = await _poisson_decisions(match, ht, record, view)
        result.append(LiveHTMatch(
            match_id=mid, home_team=home, away_team=away,
            ht_home=ht[0], ht_away=ht[1], live_home=fs.home, live_away=fs.away,
            live_minute=fs.minute, phase=match_phase(fs), league_name=league,
            kickoff_time=kickoff.isoformat() if kickoff else None,
            frozen=record is not None, frozen_at=record["frozen_at"] if record else None,
            archive_view=view, shadow=is_shadow_league(league), decisions=decisions,
        ))
    return result


@router.get("/api/live-ht/{match_id}/prediction")
async def get_live_prediction(
    match_id: str = Path(pattern=r"^[0-9]{1,12}$"),
    detail: bool = Query(False),
) -> dict:
    """Tek maçın canlı arşiv görünümü; detail=1 ile her kaynağın eşleşen maç listesi."""
    async with get_session() as session:
        match = (await session.execute(select(Match).where(
            Match.match_id == match_id, Match.deleted_at.is_(None),
        ))).scalar_one_or_none()
        if match is None:
            raise HTTPException(404, "Maç bulunamadı")
        record = (await _frozen_info(session, [match_id])).get(match_id)
        ht = (await _latest_ht_observations(session, [match_id])).get(match_id)
    if ht is None:
        snap = await get_live_snapshot()
        fs = snap.scores.get(match_id) if snap else None
        ht = observed_ht(fs) if fs else None
    if ht is None and match.actual_ht_home is not None:
        ht = (match.actual_ht_home, match.actual_ht_away)
    if ht is None:
        raise HTTPException(409, "İY skoru henüz bilinmiyor")
    view = await _view_for(match, ht, record, with_matches=detail)
    return {
        "frozen": record is not None, "frozen_at": record["frozen_at"] if record else None,
        "archive_view": view, "decisions": await _poisson_decisions(match, ht, record, view),
    }


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
    İstemci "ping" gönderirse "pong" döner. Giriş yapılmamışsa bağlantı reddedilir (4401).
    """
    from app.auth import COOKIE_NAME, auth_required, resolve

    if auth_required() and await resolve(ws.cookies.get(COOKIE_NAME)) is None:
        await ws.close(code=4401)
        return
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
