"""İY strateji sayfası (Sprint 93, ht-display-v1 — ekranda "Deneme" etiketiyle).

Günün maçları için maç öncesi İLK YARI olasılıkları ve kararları. Kickoff'a 48 saat kala dondurulan karar
(analysis_snapshots + defter) varsa o gösterilir; yoksa güncel takım modeliyle anlık hesap ("henüz kaydedilmedi").
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.analysis.league_filter import is_main_league, is_shadow_league
from app.analysis.live_poisson import get_poisson_model
from app.analysis.prematch_ht import HT_RULE_VERSION, match_ht
from app.config import ISTANBUL_TZ
from app.db.connection import get_session
from app.db.models import AnalysisSnapshot, Match

router = APIRouter()


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
            .where(Match.deleted_at.is_(None), Match.ft_scores_1.isnot(None),
                   Match.kickoff_time >= start, Match.kickoff_time < start + timedelta(days=1))
            .order_by(Match.kickoff_time)
        )).all()
        rows = [r for r in rows if is_main_league(r.league_name, r.league_code)
                or (shadow and is_shadow_league(r.league_name, r.league_code))]
        snapshots = {s.match_id: s for s in (await session.execute(
            select(AnalysisSnapshot).where(AnalysisSnapshot.rule_version == HT_RULE_VERSION,
                                           AnalysisSnapshot.match_id.in_([r.match_id for r in rows]))
        )).scalars().all()} if rows else {}
    model = await get_poisson_model() if rows else None
    matches = []
    for r in rows:
        snap = snapshots.get(r.match_id)
        if snap is not None and isinstance(snap.picks, list):
            picks = [p for p in snap.picks if not p.get("abstain")]
            probs = (snap.picks[0] or {}).get("probs") if snap.picks else None
            view = {"probs": probs, "picks": picks, "frozen": True, "frozen_at": snap.captured_at.isoformat()}
        else:
            live = match_ht(model, r.league_name or "", r.home_team, r.away_team)
            if live is None:
                continue  # ligde takım modeli yok (ilk sezon) → İY tahmini yok
            view = {**live, "frozen": False, "frozen_at": None}
        matches.append({
            "match_id": r.match_id, "home_team": r.home_team, "away_team": r.away_team,
            "league_name": r.league_name, "kickoff_time": r.kickoff_time.isoformat() if r.kickoff_time else None,
            "shadow": is_shadow_league(r.league_name, r.league_code),
            "final_ht": None if r.actual_ht_home is None else f"{r.actual_ht_home}-{r.actual_ht_away}",
            "probs": view["probs"], "picks": view["picks"], "frozen": view["frozen"],
            "frozen_at": view["frozen_at"], "league_base": view.get("league_base"),
        })
    return {"date": day.isoformat(), "rule_version": HT_RULE_VERSION, "matches": matches}
