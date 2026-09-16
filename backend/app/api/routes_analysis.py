"""Analiz ve maç detay endpoint'leri."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Path
from sqlalchemy import select

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
