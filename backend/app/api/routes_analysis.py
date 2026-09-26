"""Analiz ve maç detay endpoint'leri."""

from __future__ import annotations

import asyncio
import logging

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path
from sqlalchemy import and_, cast, func, select
from sqlalchemy.dialects.postgresql import JSONB

from app.api.schemas import AnalyzeResponse, MatchSummary
from app.api.services import (
    ANALYSIS_TIMEOUT,
    analyze_and_cache,
    cache_put,
    do_analyze,
    get_or_make_lock,
)
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/analyze/{match_id}", response_model=AnalyzeResponse)
async def get_analyze(match_id: str = Path(pattern=r"^[0-9]{1,12}$")) -> AnalyzeResponse:
    """Maçı analiz eder. Cache'te varsa anında döner, yoksa scrape eder."""
    try:
        return await asyncio.wait_for(analyze_and_cache(match_id), timeout=ANALYSIS_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Analiz zaman aşımına uğradı")


@router.post("/api/analyze/{match_id}", response_model=AnalyzeResponse)
async def post_analyze(match_id: str = Path(pattern=r"^[0-9]{1,12}$")) -> AnalyzeResponse:
    """Maçı her zaman scrape eder ve cache'i günceller."""
    async def refresh():
        async with get_or_make_lock(match_id):
            response = await do_analyze(match_id)
            cache_put(match_id, response)
            return response

    try:
        return await asyncio.wait_for(refresh(), timeout=ANALYSIS_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Analiz zaman aşımına uğradı")


@router.get("/api/match/{match_id}", response_model=MatchSummary)
async def get_match(match_id: str = Path(pattern=r"^[0-9]{1,12}$")) -> MatchSummary:
    """Maçın özet bilgisi. DB'de yoksa Playwright ile çek + DB'ye kaydet, sonra dön."""
    async with get_session() as session:
        row = (
            await session.execute(
                select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
            )
        ).scalar_one_or_none()

    if not row:
        log.info("/api/match miss — Playwright fallback: %s", match_id)
        try:
            await asyncio.wait_for(do_analyze(match_id), timeout=25.0)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail=f"Maç verisi çekilemedi (timeout): {match_id}")
        except Exception as exc:
            log.warning("Maç fallback scrape başarısız [%s]: %s", match_id, exc)
            raise HTTPException(status_code=404, detail=f"Maç bulunamadı: {match_id}")

        async with get_session() as session:
            row = (
                await session.execute(
                    select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail=f"Maç bulunamadı: {match_id}")

    return MatchSummary(
        match_id=row.match_id,
        home_team=row.home_team,
        away_team=row.away_team,
        league_code=row.league_code,
        season=row.season,
        actual_ft_home=row.actual_ft_home,
        actual_ft_away=row.actual_ft_away,
        actual_ht_home=row.actual_ht_home,
        actual_ht_away=row.actual_ht_away,
        ft_scores_1=row.ft_scores_1,
        ft_scores_x=row.ft_scores_x,
        ft_scores_2=row.ft_scores_2,
    )


@router.get("/api/analyze/{match_id}/matched-matches")
async def get_matched_matches(
    match_id: str = Path(pattern=r"^[0-9]{1,12}$"),
) -> dict:
    """Analiz edilen maçın arşivde eşleşen maçlarını döndürür (B ve C)."""
    now = datetime.now(timezone.utc)

    async with get_session() as session:
        target = (
            await session.execute(
                select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
            )
        ).scalar_one_or_none()

    if not target:
        raise HTTPException(404, "Maç bulunamadı")

    known_at = func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at)
    base_filters = [
        Match.match_id != match_id,
        Match.deleted_at.is_(None),
        Match.actual_ft_home.isnot(None),
        Match.actual_ft_away.isnot(None),
        Match.kickoff_time < now,
        known_at > Match.kickoff_time,
        known_at <= now,
        Match.analyzed_at.is_not(None),
        Match.analyzed_at < Match.kickoff_time,
    ]
    detail_cols = [
        Match.match_id, Match.home_team, Match.away_team, Match.league_code,
        Match.actual_ht_home, Match.actual_ht_away,
        Match.actual_ft_home, Match.actual_ft_away,
        Match.kickoff_time,
    ]

    def _row_to_dict(r) -> dict:
        ht_h, ht_a = r.actual_ht_home, r.actual_ht_away
        ft_h, ft_a = r.actual_ft_home, r.actual_ft_away
        h2_h = ft_h - ht_h if ht_h is not None and ft_h is not None else None
        h2_a = ft_a - ht_a if ht_a is not None and ft_a is not None else None
        return {
            "match_id": r.match_id,
            "home_team": r.home_team,
            "away_team": r.away_team,
            "league_code": r.league_code,
            "ht": f"{ht_h}-{ht_a}" if ht_h is not None else None,
            "h2": f"{h2_h}-{h2_a}" if h2_h is not None else None,
            "ft": f"{ft_h}-{ft_a}" if ft_h is not None else None,
            "kickoff_time": r.kickoff_time.isoformat() if r.kickoff_time else None,
        }

    archive_b: list[dict] = []
    archive_c: list[dict] = []

    if target.ft_scores_1 and target.ft_scores_x and target.ft_scores_2:
        async with get_session() as session:
            b_filters = [
                *base_filters,
                Match.ft_scores_1.cast(JSONB) == cast(target.ft_scores_1, JSONB),
                Match.ft_scores_x.cast(JSONB) == cast(target.ft_scores_x, JSONB),
                Match.ft_scores_2.cast(JSONB) == cast(target.ft_scores_2, JSONB),
            ]
            rows = (await session.execute(select(*detail_cols).where(*b_filters).limit(50))).all()
            archive_b = [_row_to_dict(r) for r in rows]

    if target.ft_all_ratios:
        async with get_session() as session:
            c_filters = [
                *base_filters,
                cast(Match.ft_all_ratios, JSONB) == cast(target.ft_all_ratios, JSONB),
            ]
            rows = (await session.execute(select(*detail_cols).where(*c_filters).limit(50))).all()
            archive_c = [_row_to_dict(r) for r in rows]

    return {"archive_b": archive_b, "archive_c": archive_c}
