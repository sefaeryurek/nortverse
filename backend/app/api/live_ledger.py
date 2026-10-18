"""Canlı İY→MS tahminlerini devre arasında bir kez dondurur (değişmez defter).

İzleyici WebSocket yayınından bağımsız çalışır — sayfayı kimse açmasa da kayıt alınır.
Sadece başlama saati [şimdi−150dk, şimdi−40dk] aralığında analiz edilmiş maç varken
canlı skor görüntüsünü okur.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.analysis.ledger import record_predictions
from app.analysis.live_model import LIVE_RULE_VERSION, get_cond_table, predict_live
from app.analysis.persist import hash_string
from app.api.live_snapshot import get_live_snapshot
from app.db.connection import get_session
from app.db.models import Match, MatchHtObservation, PredictionLedger
from app.scraper.fixture_scores import FixtureScore, phase_from_minute

log = logging.getLogger(__name__)

WATCH_INTERVAL = 60.0
WINDOW_START = timedelta(minutes=150)
WINDOW_END = timedelta(minutes=40)
_OBS_SOURCE = "livescore"

_watcher_task: asyncio.Task | None = None


def match_phase(fs: FixtureScore) -> str | None:
    return fs.phase or phase_from_minute(fs.minute)


def observed_ht(fs: FixtureScore) -> tuple[int, int] | None:
    """Devre arasında anlık skor = İY skoru; 2. yarıda panonun İY alanı."""
    phase = match_phase(fs)
    if phase == "ht" and fs.home is not None and fs.away is not None:
        return fs.home, fs.away
    if phase == "2h" and fs.ht_home is not None and fs.ht_away is not None:
        return fs.ht_home, fs.ht_away
    return None


def pattern_hash(match: Match) -> str | None:
    return hash_string({f: getattr(match, f"pattern_{f}_hash") for f in "bcd"})


def ledger_rows(match: Match, prediction: dict, as_of: datetime, ht_observation_id: int,
                late: bool) -> list[dict]:
    """Tahmin sözlüğünden defter satırları (MS 1X2 + uygunsa MS Ü2.5 ve KG)."""
    ht = prediction["ht"]
    common = {
        "source": "live_ht", "rule_version": LIVE_RULE_VERSION, "pattern_hash": pattern_hash(match),
        "match_id": match.match_id, "league_name": match.league_name or "",
        "kickoff_time": match.kickoff_time, "as_of": as_of, "period": "ft",
        "ht_home": ht["home"], "ht_away": ht["away"], "ht_observation_id": ht_observation_id,
    }
    ms = prediction["ms"]
    rows = [{
        **common, "market": "result", "selection": ms["pick"],
        "prob_shown_bp": round(ms["prob"] * 10000),
        "prob_raw_bp": round(ms["ht_baseline"]["probs"][ms["pick"]] * 10000),
        "baseline_selection": ms["ht_baseline"]["pick"],
        "baseline_prob_bp": round(ms["ht_baseline"]["prob"] * 10000),
        "confidence_tier": ms["tier"], "sample_n": ms["n"] or None,
        "details": {**prediction, "late": late},
    }]
    for market, key in (("ou_25", "over25"), ("kg", "btts")):
        block = prediction[key]
        if block.get("applicable"):
            rows.append({
                **common, "market": market, "selection": block["pick"],
                "prob_shown_bp": round(block["prob"] * 10000),
                "confidence_tier": block["tier"], "sample_n": block["n"] or None,
                "details": {key: block, "late": late},
            })
    return rows


async def _ht_observation_id(session, match: Match, ht: tuple[int, int], phase: str,
                             observed_at: datetime) -> int:
    revision = f"{ht[0]}-{ht[1]}"
    inserted = await session.execute(
        insert(MatchHtObservation).values(
            match_id=match.match_id, kickoff_time=match.kickoff_time,
            ht_home=ht[0], ht_away=ht[1], phase="ht_break" if phase == "ht" else "second_half",
            observed_at=observed_at, source=_OBS_SOURCE, source_revision=revision,
        ).on_conflict_do_nothing(constraint="uq_match_ht_observations_source_revision")
        .returning(MatchHtObservation.id)
    )
    obs_id = inserted.scalar_one_or_none()
    if obs_id is None:
        obs_id = (await session.execute(
            select(MatchHtObservation.id).where(
                MatchHtObservation.match_id == match.match_id,
                MatchHtObservation.source == _OBS_SOURCE,
                MatchHtObservation.source_revision == revision,
            )
        )).scalar_one()
    return obs_id


async def plan_live_freeze(match: Match, fs: FixtureScore) -> tuple[str, dict | None]:
    """Dondurma kararı (yazmadan): ('ready', tahmin) ya da (neden, None)."""
    ht = observed_ht(fs)
    phase = match_phase(fs)
    if ht is None or phase not in ("ht", "2h"):
        return "no_ht", None
    if match.kickoff_time is None or datetime.now(timezone.utc) <= match.kickoff_time:
        return "not_started", None
    if phase == "2h" and (fs.home, fs.away) != ht:
        # 2. yarıda gol gördükten sonra "tahmin" yazılmaz.
        return "late_score_changed", None
    table = await get_cond_table()
    prediction = predict_live(
        table, match.league_name or "", ht,
        [match.pattern_ft_b, match.pattern_ft_c, match.pattern_ft_d],
    )
    return "ready", prediction


async def freeze_live_prediction(match: Match, fs: FixtureScore, *, dry_run: bool = False,
                                 report: dict | None = None) -> str:
    """İY gözlemini ve tahmini bir kez kaydeder. Durum kodunu döner (tahmin `report`'a yazılır)."""
    status, prediction = await plan_live_freeze(match, fs)
    if report is not None:
        report["prediction"] = prediction
    if status == "late_score_changed":
        log.info("Canlı tahmin dondurulmadı (2. yarıda skor değişmiş) [%s]", match.match_id)
    if status != "ready":
        return status
    if dry_run:
        return "dry_run"
    ht = observed_ht(fs)
    phase = match_phase(fs)
    now = datetime.now(timezone.utc)
    async with get_session() as session:
        obs_id = await _ht_observation_id(session, match, ht, phase, now)
        written = await record_predictions(
            session, ledger_rows(match, prediction, now, obs_id, late=phase == "2h"))
    if written:
        log.info("Canlı tahmin donduruldu [%s] İY %s-%s → %s %%%.1f",
                 match.match_id, ht[0], ht[1], prediction["ms"]["pick"], prediction["ms"]["prob"] * 100)
        return "frozen"
    return "already_frozen"


async def run_tick(*, dry_run: bool = False, snapshot=None) -> list[dict]:
    """İzleyicinin bir turu. Her aday maç için {match, score, status, prediction} döner.

    `snapshot` verilmezse süreç içi canlı görüntü kullanılır (CLI tam yenilenmiş görüntü verir).
    """
    now = datetime.now(timezone.utc)
    async with get_session() as session:
        candidates = (await session.execute(
            select(Match).where(
                Match.deleted_at.is_(None),
                Match.ft_scores_1.isnot(None),
                Match.kickoff_time >= now - WINDOW_START,
                Match.kickoff_time <= now - WINDOW_END,
            ).order_by(Match.kickoff_time)
        )).scalars().all()
        if not candidates:
            return []
        frozen = set((await session.execute(
            select(PredictionLedger.match_id).where(
                PredictionLedger.source == "live_ht",
                PredictionLedger.rule_version == LIVE_RULE_VERSION,
                PredictionLedger.match_id.in_([m.match_id for m in candidates]),
            )
        )).scalars().all())
    report = [{"match": m, "score": None, "status": "already_frozen", "prediction": None}
              for m in candidates if m.match_id in frozen]
    pending = [m for m in candidates if m.match_id not in frozen]
    if not pending:
        return report
    if snapshot is None:
        snapshot = await get_live_snapshot()
    for match in pending:
        entry = {"match": match, "score": None, "status": "no_snapshot", "prediction": None}
        report.append(entry)
        if snapshot is None:
            continue
        fs = snapshot.scores.get(match.match_id)
        entry["score"] = fs
        if fs is None or fs.status != "live":
            entry["status"] = "not_live"
            continue
        try:
            entry["status"] = await freeze_live_prediction(match, fs, dry_run=dry_run, report=entry)
        except Exception:
            entry["status"] = "error"
            log.warning("Canlı tahmin dondurulamadı [%s]", match.match_id, exc_info=True)
    return report


async def _tick() -> None:
    await run_tick()


async def _watch_loop() -> None:
    while True:
        try:
            await _tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.warning("Canlı defter izleyicisi hatası", exc_info=True)
        await asyncio.sleep(WATCH_INTERVAL)


def start_live_watcher() -> None:
    global _watcher_task
    if _watcher_task is None or _watcher_task.done():
        _watcher_task = asyncio.create_task(_watch_loop())
        log.info("Canlı defter izleyicisi başlatıldı (%.0fs)", WATCH_INTERVAL)


async def stop_live_watcher() -> None:
    global _watcher_task
    task = _watcher_task
    _watcher_task = None
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
