"""Canlı İY Eşleşme — devre arasındaki maçlar için arşiv istatistikleri.

Sprint 47: Devre arasında (veya 2. yarı ilk 15dk) olan maçların İY skorunu
arşivdeki geçmiş maçlarla karşılaştırıp MS ve 2Y tahminleri üretir.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import Integer, func, select

from app.api.live_snapshot import get_live_snapshot
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)
router = APIRouter()

_ht_observed: dict[str, tuple[int, int]] = {}
_ht_observed_day: str = ""

_stats_cache: dict[str, tuple[float, dict]] = {}
_STATS_TTL = 3600.0


class LiveHTMatch(BaseModel):
    match_id: str
    home_team: str | None = None
    away_team: str | None = None
    ht_home: int
    ht_away: int
    live_minute: str | None = None
    league_name: str | None = None
    kickoff_time: str | None = None


class TopFTScore(BaseModel):
    score: str
    count: int
    pct: float


class LiveHTStats(BaseModel):
    ht_score: str
    archive_count: int
    ft_result_1_pct: float = 0.0
    ft_result_x_pct: float = 0.0
    ft_result_2_pct: float = 0.0
    ft_ust_25_pct: float = 0.0
    ft_kg_var_pct: float = 0.0
    h2_result_1_pct: float = 0.0
    h2_result_x_pct: float = 0.0
    h2_result_2_pct: float = 0.0
    top_ft_scores: list[TopFTScore] = []


def _is_ht_window(minute: str | None) -> bool:
    if not minute:
        return False
    if minute == "HT":
        return True
    try:
        base = int(minute.split("+")[0])
        return 46 <= base <= 60
    except (ValueError, IndexError):
        return False


def _cleanup_observed() -> None:
    global _ht_observed_day
    today = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d")
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
        if fs.minute == "HT" and fs.home is not None and fs.away is not None:
            _ht_observed[mid] = (fs.home, fs.away)
            result.append(LiveHTMatch(
                match_id=mid,
                ht_home=fs.home,
                ht_away=fs.away,
                live_minute=fs.minute,
            ))
        elif _is_ht_window(fs.minute) and mid in _ht_observed:
            ht_h, ht_a = _ht_observed[mid]
            result.append(LiveHTMatch(
                match_id=mid,
                ht_home=ht_h,
                ht_away=ht_a,
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
            info = {r[0]: r for r in rows}
        for m in result:
            r = info.get(m.match_id)
            if r:
                m.home_team = r[1]
                m.away_team = r[2]
                m.league_name = r[3]
                m.kickoff_time = r[4].isoformat() if r[4] else None
    return result


@router.get("/api/live-ht/{ht_home}-{ht_away}/stats")
async def get_live_ht_stats(ht_home: int, ht_away: int) -> LiveHTStats:
    if ht_home < 0 or ht_away < 0 or ht_home > 15 or ht_away > 15:
        raise HTTPException(400, "Geçersiz İY skoru")

    cache_key = f"{ht_home}-{ht_away}"
    now = time.monotonic()
    if cache_key in _stats_cache:
        cached_at, cached_data = _stats_cache[cache_key]
        if (now - cached_at) < _STATS_TTL:
            return LiveHTStats(**cached_data)

    async with get_session() as session:
        stmt = select(
            Match.actual_ft_home,
            Match.actual_ft_away,
            Match.actual_h2_home,
            Match.actual_h2_away,
        ).where(
            Match.actual_ht_home == ht_home,
            Match.actual_ht_away == ht_away,
            Match.actual_ft_home.isnot(None),
            Match.actual_ft_away.isnot(None),
            Match.deleted_at.is_(None),
        )
        rows = (await session.execute(stmt)).all()

    count = len(rows)
    if count == 0:
        data = {"ht_score": cache_key, "archive_count": 0}
        _stats_cache[cache_key] = (now, data)
        return LiveHTStats(**data)

    ft_1, ft_x, ft_2 = 0, 0, 0
    ust_25, kg_var = 0, 0
    h2_1, h2_x, h2_2 = 0, 0, 0
    score_counts: dict[str, int] = {}

    for ft_h, ft_a, h2_h, h2_a in rows:
        if ft_h > ft_a:
            ft_1 += 1
        elif ft_h == ft_a:
            ft_x += 1
        else:
            ft_2 += 1

        total = ft_h + ft_a
        if total > 2:
            ust_25 += 1
        if ft_h > 0 and ft_a > 0:
            kg_var += 1

        score_str = f"{ft_h}-{ft_a}"
        score_counts[score_str] = score_counts.get(score_str, 0) + 1

        if h2_h is not None and h2_a is not None:
            if h2_h > h2_a:
                h2_1 += 1
            elif h2_h == h2_a:
                h2_x += 1
            else:
                h2_2 += 1

    top_scores = sorted(score_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    data = {
        "ht_score": cache_key,
        "archive_count": count,
        "ft_result_1_pct": round(ft_1 / count * 100, 1),
        "ft_result_x_pct": round(ft_x / count * 100, 1),
        "ft_result_2_pct": round(ft_2 / count * 100, 1),
        "ft_ust_25_pct": round(ust_25 / count * 100, 1),
        "ft_kg_var_pct": round(kg_var / count * 100, 1),
        "h2_result_1_pct": round(h2_1 / count * 100, 1),
        "h2_result_x_pct": round(h2_x / count * 100, 1),
        "h2_result_2_pct": round(h2_2 / count * 100, 1),
        "top_ft_scores": [
            {"score": s, "count": c, "pct": round(c / count * 100, 1)}
            for s, c in top_scores
        ],
    }
    _stats_cache[cache_key] = (now, data)
    return LiveHTStats(**data)
