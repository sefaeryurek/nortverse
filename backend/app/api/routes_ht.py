"""İY oran panosu (Sprint 93 — kullanıcı kararı 27 Ekim: "Oran panosu").

Ölçüm: takım gücü modeli İY'de Bet365 kapanışını yenemedi (1.205 maç, Şub–Eki 2026: piyasa log-loss 1,0225,
model 1,0371; "değerli" görünen seçimler testte %12–30 zarar). Bu yüzden ana bilgi piyasanın kendisi:
sitenin açtığı İY pazarları (1/X/2 + İY Asya Ü/A çizgisi), Bet365 oranı ve oranın ima ettiği olasılık
(bahis payı çıkarılmış). Model olasılığı ikincil not. "Value" iddiası yok.

Maç öncesi İY model kararları (ht-display-v1) arka planda dondurulup deftere yazılmaya devam eder.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.analysis.ht_value import settle
from app.analysis.league_filter import is_main_league, is_shadow_league
from app.analysis.live_poisson import get_poisson_model
from app.analysis.prematch_ht import HT_RULE_VERSIONS, match_ht
from app.config import ISTANBUL_TZ
from app.db.connection import get_session
from app.db.models import AnalysisSnapshot, Match
from app.scraper.odds import latest_prematch, market_options, opening_prematch, with_opening

log = logging.getLogger(__name__)
router = APIRouter()

ODDS_MAX_AGE_S = 15 * 60   # yaklaşan maçta oran 15 dk'da bir arka planda tazelenir
FETCH_TIMEOUT_S = 15.0
# Sprint 94 K-1: sayfa artık kaynağı beklemez (eskiden kaydı olmayan maç için 8 sn bekliyor, hafta sonu 36 maçın
# 12–14'ü yükleniyordu). Oranlar ön çekimle hazır; eksik olan arka planda çekilir, sayfada "oran yükleniyor".
_inflight: dict[str, asyncio.Task] = {}


def _spawn(match_id: str) -> asyncio.Task:
    """Aynı maç için tek paylaşılan yenileme görevi (eskiden ikinci istek None alıp maçı listeden düşürüyordu)."""
    task = _inflight.get(match_id)
    if task is None or task.done():
        task = asyncio.create_task(_do_refresh(match_id))
        _inflight[match_id] = task
        task.add_done_callback(lambda _t, m=match_id: _inflight.pop(m, None) if _inflight.get(m) is _t else None)
    return task


async def _refresh(match_id: str) -> dict | None:
    return await asyncio.shield(_spawn(match_id))


async def _do_refresh(match_id: str) -> dict | None:
    """Kaynaktan çeker (DB oturumu kapalıyken), sonra kısa bir oturumla yazar."""
    from app.scraper.odds import fetch_odds, store_history

    try:
        history = await asyncio.wait_for(fetch_odds(match_id, half=True), timeout=FETCH_TIMEOUT_S)
    except Exception as exc:  # ağ / kaynak
        log.info("İY oranı alınamadı [%s]: %s", match_id, exc)
        return None
    async with get_session() as session:
        return await store_history(session, match_id, "ht", history, datetime.now(timezone.utc))


async def _stored_odds(match_ids: list[str]) -> dict[str, tuple[datetime, dict]]:
    from app.db.models import MatchOdds

    if not match_ids:
        return {}
    async with get_session() as session:
        rows = (await session.execute(
            select(MatchOdds.match_id, MatchOdds.fetched_at, MatchOdds.history)
            .where(MatchOdds.scope == "ht", MatchOdds.match_id.in_(match_ids))
        )).all()
    return {r.match_id: (r.fetched_at, r.history) for r in rows}


async def _odds_by_match(rows) -> tuple[dict[str, dict], dict[str, dict], set[str]]:
    """Sadece DB: (maç → maç öncesi son oranlar, maç → ham geçmiş, henüz oranı gelmemiş maçlar).

    Eski ya da hiç olmayan oran arka planda tazelenir; sayfa beklemez.
    """
    now = datetime.now(timezone.utc)
    stored = await _stored_odds([r.match_id for r in rows])
    history: dict[str, dict] = {}
    pending: set[str] = set()
    for r in rows:
        finished = r.actual_ht_home is not None
        if r.match_id in stored:
            fetched_at, hist = stored[r.match_id]
            history[r.match_id] = hist
            stale = (now - fetched_at).total_seconds() > ODDS_MAX_AGE_S
            # biten maçta kapanış yeter; başlamış/yaklaşan maçta eskiyse arka planda tazele
            if stale and not (finished and fetched_at > r.kickoff_time):
                _spawn(r.match_id)
        elif not finished:
            pending.add(r.match_id)
            _spawn(r.match_id)
    out = {}
    for r in rows:
        started = r.kickoff_time is not None and r.kickoff_time <= now
        out[r.match_id] = latest_prematch(history.get(r.match_id), before=r.kickoff_time if started else None)
    return out, history, pending


# Sprint 94 I2: yaklaşan maçların İY oranları önceden çekilir — sayfa açılınca beklemesin (kaydı olmayan maç için
# 8 sn bekliyordu). Backend içinde 15 dk'da bir; istekler kapılı istemciden (saniyede ~1) sırayla geçer.
PREFETCH_EVERY_S = 15 * 60
PREFETCH_HORIZON = timedelta(hours=12)
PREFETCH_MAX = 60
_prefetch_task: asyncio.Task | None = None


async def prefetch_upcoming(now: datetime | None = None) -> int:
    """Önümüzdeki 12 saatte başlayacak ana lig maçlarından İY oranı olmayan ya da 15 dk'dan eski olanları çeker."""
    now = now or datetime.now(timezone.utc)
    async with get_session() as session:
        rows = (await session.execute(
            select(Match.match_id, Match.league_name, Match.league_code)
            .where(Match.deleted_at.is_(None), Match.kickoff_time > now, Match.kickoff_time <= now + PREFETCH_HORIZON)
            .order_by(Match.kickoff_time)
        )).all()
    ids = [r.match_id for r in rows if is_main_league(r.league_name, r.league_code)]
    stored = await _stored_odds(ids)
    due = [mid for mid in ids
           if mid not in stored or (now - stored[mid][0]).total_seconds() > ODDS_MAX_AGE_S][:PREFETCH_MAX]
    for mid in due:
        await _refresh(mid)
    return len(due)


async def _prefetch_loop() -> None:
    while True:
        try:
            count = await prefetch_upcoming()
            if count:
                log.info("İY oranları önceden çekildi: %d maç", count)
        except Exception:
            log.warning("İY oran ön çekimi başarısız", exc_info=True)
        await asyncio.sleep(PREFETCH_EVERY_S)


def start_ht_prefetch() -> None:
    global _prefetch_task
    if _prefetch_task is None or _prefetch_task.done():
        _prefetch_task = asyncio.create_task(_prefetch_loop())


async def stop_ht_prefetch() -> None:
    global _prefetch_task
    task, _prefetch_task = _prefetch_task, None
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def _with_model(options: list[dict], probs: dict | None) -> list[dict]:
    """İY 1/X/2 seçeneklerine modelin olasılığını ekler (Ü/A'da çizgi iadeli olduğu için kıyas anlamlı değil)."""
    result = (probs or {}).get("result") or {}
    return [{**o, "model_pct": result.get(o["selection"]) if o["market"] == "result" else None} for o in options]


@router.get("/api/ht-strategy")
async def ht_strategy(
    target_date: str | None = Query(None, alias="date"),
    shadow: bool = Query(False, description="Gölgedeki ligleri de listele (deneme)"),
) -> dict:
    try:
        day = date.fromisoformat(target_date) if target_date else datetime.now(ISTANBUL_TZ).date()
    except ValueError:
        raise HTTPException(400, "Geçersiz tarih (YYYY-MM-DD)")
    start = datetime.combine(day, datetime.min.time(), ISTANBUL_TZ)
    async with get_session() as session:
        rows = (await session.execute(
            select(Match.match_id, Match.home_team, Match.away_team, Match.league_name, Match.league_code,
                   Match.kickoff_time, Match.actual_ht_home, Match.actual_ht_away)
            .where(Match.deleted_at.is_(None), Match.kickoff_time >= start,
                   Match.kickoff_time < start + timedelta(days=1))
            .order_by(Match.kickoff_time)
        )).all()
        rows = [r for r in rows if is_main_league(r.league_name, r.league_code)
                or (shadow and is_shadow_league(r.league_name, r.league_code))]
        # Sürüm sırasıyla: aynı maçta hem v1 hem v1.1 varsa yenisi kazanır
        snapshots = {s.match_id: s for s in sorted((await session.execute(
            select(AnalysisSnapshot).where(AnalysisSnapshot.rule_version.in_(HT_RULE_VERSIONS),
                                           AnalysisSnapshot.match_id.in_([r.match_id for r in rows]))
        )).scalars().all(), key=lambda s: HT_RULE_VERSIONS.index(s.rule_version))} if rows else {}
    model = await get_poisson_model() if rows else None
    odds_by_match, histories, pending = await _odds_by_match(rows)
    matches = []
    for r in rows:
        odds = odds_by_match.get(r.match_id) or {}
        options = market_options(odds)
        if not options:
            if r.match_id in pending:  # oran arka planda çekiliyor → yer tutucu kart
                matches.append({
                    "match_id": r.match_id, "home_team": r.home_team, "away_team": r.away_team,
                    "league_name": r.league_name,
                    "kickoff_time": r.kickoff_time.isoformat() if r.kickoff_time else None,
                    "shadow": is_shadow_league(r.league_name, r.league_code), "final_ht": None,
                    "options": [], "odds_at": None, "expected_goals": None, "odds_pending": True,
                })
            continue  # site bu maçta İY oranı açmamış
        snap = snapshots.get(r.match_id)
        if snap is not None and isinstance(snap.picks, list) and snap.picks:
            probs = (snap.picks[0] or {}).get("probs")
        else:
            live = match_ht(model, r.league_name or "", r.home_team, r.away_team)
            probs = live["probs"] if live else None
        options = sorted(with_opening(_with_model(options, probs), opening_prematch(histories.get(r.match_id))),
                         key=lambda o: -o["pct"])
        final = None if r.actual_ht_home is None else (r.actual_ht_home, r.actual_ht_away)
        if final is not None:
            for o in options:
                profit = settle(o, final)
                o["outcome"] = "hit" if profit > 0 else "push" if profit == 0 else "half" if profit > -1 else "miss"
        matches.append({
            "match_id": r.match_id, "home_team": r.home_team, "away_team": r.away_team,
            "league_name": r.league_name, "kickoff_time": r.kickoff_time.isoformat() if r.kickoff_time else None,
            "shadow": is_shadow_league(r.league_name, r.league_code),
            "final_ht": None if final is None else f"{final[0]}-{final[1]}",
            "options": options, "odds_at": (odds.get("op") or odds.get("ou") or {}).get("mt"),
            "expected_goals": (probs or {}).get("lambda"), "top_scores": (probs or {}).get("top_scores"),
        })
    matches.sort(key=lambda m: -(m["options"][0]["pct"] if m["options"] else 0))
    return {"date": day.isoformat(), "matches": matches}
