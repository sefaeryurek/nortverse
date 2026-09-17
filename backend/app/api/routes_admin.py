"""Yönetim endpoint'leri: health, quality, correlations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter
from sqlalchemy import func, or_, select

from app.analysis.correlation import compute_poisson_correlations
from app.analysis.league_filter import is_supported_league
from app.api.schemas import DataQuality, HealthResponse
from app.api.services import analysis_cache, bg_queue
from app.db.connection import get_session
from app.db.models import FixtureCache, Match

log = logging.getLogger(__name__)
router = APIRouter()

_corr_cache: dict[str, float] | None = None


@router.api_route("/api/health", methods=["GET", "HEAD"], response_model=HealthResponse)
async def health() -> HealthResponse:
    """Sistem sağlık kontrolü — UptimeRobot/cron-job.org dış pinglerine uygun."""
    db_ok = False
    last_pipeline: Optional[datetime] = None
    last_fixture_cached: Optional[datetime] = None

    try:
        async with get_session() as session:
            row = await session.execute(select(func.max(Match.analyzed_at)))
            last_pipeline = row.scalar_one_or_none()

            fc = await session.get(FixtureCache, datetime.now(timezone(timedelta(hours=3))).date().isoformat())
            if fc:
                last_fixture_cached = fc.cached_at

            db_ok = True
    except Exception as exc:
        log.warning("Health check DB sorgusu başarısız: %s", exc)

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db_ok=db_ok,
        last_pipeline_at=last_pipeline.isoformat() if last_pipeline else None,
        last_fixture_cached_at=last_fixture_cached.isoformat() if last_fixture_cached else None,
        bg_queue_size=bg_queue.qsize() if bg_queue else 0,
        cached_analyses=len(analysis_cache),
    )


@router.get("/api/admin/quality", response_model=DataQuality)
async def admin_quality() -> DataQuality:
    """Detaylı veri kalitesi raporu."""
    async with get_session() as session:
        total = (await session.execute(select(func.count(Match.id)))).scalar() or 0
        active = (await session.execute(
            select(func.count(Match.id)).where(Match.deleted_at.is_(None))
        )).scalar() or 0
        soft_deleted = total - active

        active_rows = (await session.execute(
            select(Match.league_code, Match.league_name)
            .where(Match.deleted_at.is_(None))
        )).all()
        non_league = sum(
            1 for r in active_rows
            if not is_supported_league(r.league_name, r.league_code)
        )

        missing_pattern = (await session.execute(
            select(func.count(Match.id)).where(
                Match.deleted_at.is_(None), Match.pattern_computed_at.is_(None),
            )
        )).scalar() or 0
        missing_trends = (await session.execute(
            select(func.count(Match.id)).where(
                Match.deleted_at.is_(None), Match.trends.is_(None)
            )
        )).scalar() or 0
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=130)
        missing_actual = (await session.execute(
            select(func.count(Match.id)).where(
                Match.deleted_at.is_(None),
                Match.kickoff_time < cutoff,
                or_(Match.actual_ft_home.is_(None), Match.actual_ft_away.is_(None)),
            )
        )).scalar() or 0

    if active == 0:
        score = 0.0
    else:
        penalties = (
            (non_league / max(total, 1)) * 40
            + (missing_pattern / max(active, 1)) * 20
            + (missing_actual / max(active, 1)) * 30
            + (missing_trends / max(active, 1)) * 10
        )
        score = max(0.0, 100.0 - penalties)

    return DataQuality(
        total_matches=total,
        active_matches=active,
        soft_deleted=soft_deleted,
        non_league_active=non_league,
        missing_pattern=missing_pattern,
        missing_trends=missing_trends,
        missing_actual_score=missing_actual,
        quality_score=round(score, 1),
    )


@router.get("/api/correlations")
async def get_correlations() -> dict[str, float]:
    """Poisson model korelasyon faktörleri (statik, hesaplama bir kez yapılır)."""
    global _corr_cache
    if _corr_cache is None:
        _corr_cache = compute_poisson_correlations()
    return _corr_cache
