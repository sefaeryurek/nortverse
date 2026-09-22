"""Yönetim endpoint'leri: health, quality, correlations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter
from sqlalchemy import case, func, or_, select, text

from app.analysis.correlation import compute_poisson_correlations
from app.analysis.league_filter import CUP_KEYWORDS, is_supported_league
from app.analysis.snapshots import RULE_VERSION
from app.api.schemas import AnalysisEvidence, AnalysisValidation, DataQuality, HealthResponse, MarketValidation
from app.api.services import analysis_cache, bg_queue
from app.db.connection import get_session
from app.db.models import FixtureCache, Match

log = logging.getLogger(__name__)
router = APIRouter()

_corr_cache: dict[str, float] | None = None

_RESOLVED_SNAPSHOT = """
    m.deleted_at IS NULL
    AND m.actual_ft_home IS NOT NULL AND m.actual_ft_away IS NOT NULL
    AND m.result_fetched_at > s.kickoff_time
    AND s.captured_at < s.kickoff_time
"""

_VALIDATION_COUNTS = text(f"""
    SELECT count(*), count(*) FILTER (WHERE {_RESOLVED_SNAPSHOT})
    FROM analysis_snapshots s
    LEFT JOIN matches m ON m.match_id = s.match_id
    WHERE s.rule_version = :rule_version
""")

_VALIDATION_MARKETS = text(f"""
    SELECT p.value->>'archive' AS archive, p.value->>'market' AS market,
           count(*) AS evaluated,
           count(*) FILTER (WHERE
               CASE
                   WHEN p.value->>'market' = 'result' THEN
                       (p.value->>'selection' = '1' AND m.actual_ft_home > m.actual_ft_away)
                       OR (p.value->>'selection' = 'X' AND m.actual_ft_home = m.actual_ft_away)
                       OR (p.value->>'selection' = '2' AND m.actual_ft_home < m.actual_ft_away)
                   WHEN p.value->>'market' = 'over_25' THEN
                       (p.value->>'selection' = 'over') =
                       (m.actual_ft_home + m.actual_ft_away > 2)
                   WHEN p.value->>'market' = 'btts' THEN
                       (p.value->>'selection' = 'yes') =
                       (m.actual_ft_home > 0 AND m.actual_ft_away > 0)
                   ELSE false
               END
           ) AS hits
    FROM analysis_snapshots s
    JOIN matches m ON m.match_id = s.match_id
    CROSS JOIN LATERAL jsonb_array_elements(s.picks) AS p(value)
    WHERE s.rule_version = :rule_version AND {_RESOLVED_SNAPSHOT}
    GROUP BY p.value->>'archive', p.value->>'market'
    ORDER BY archive, market
""")


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


@router.get("/api/analysis-evidence", response_model=AnalysisEvidence)
async def analysis_evidence() -> AnalysisEvidence:
    """Count only analyses saved before kickoff and matches with a final score.

    JSONB null is distinct from SQL NULL, so count actual pattern objects.
    This reports coverage; it does not claim a calibrated hit rate.
    """
    eligible = (
        Match.deleted_at.is_(None),
        Match.actual_ft_home.is_not(None),
        Match.actual_ft_away.is_not(None),
        Match.result_fetched_at.is_not(None),
        Match.kickoff_time.is_not(None),
        Match.analyzed_at.is_not(None),
        Match.pattern_computed_at.is_not(None),
        Match.analyzed_at < Match.kickoff_time,
        Match.pattern_computed_at < Match.kickoff_time,
        Match.result_fetched_at > Match.kickoff_time,
    )
    league_fields = (Match.league_name, Match.league_code)
    league_filter = tuple(
        ~func.lower(func.coalesce(field, "")).contains(keyword)
        for field in league_fields for keyword in CUP_KEYWORDS
    )
    score_columns = (Match.ft_scores_1, Match.ft_scores_x, Match.ft_scores_2)
    shortlist = or_(*(case(
        (func.jsonb_typeof(column) == "array", func.jsonb_array_length(column)), else_=0,
    ) > 0 for column in score_columns))
    final_score = func.concat(Match.actual_ft_home, "-", Match.actual_ft_away)
    exact_hit = or_(*(func.jsonb_exists(column, final_score) for column in score_columns))
    async with get_session() as session:
        row = (await session.execute(
            select(
                func.count(Match.id),
                func.count(Match.id).filter(func.jsonb_typeof(Match.pattern_ft_b) == "object"),
                func.count(Match.id).filter(func.jsonb_typeof(Match.pattern_ft_c) == "object"),
                func.count(Match.id).filter(shortlist),
                func.count(Match.id).filter(exact_hit),
            ).where(*eligible, *league_filter)
        )).one()
    return AnalysisEvidence(
        eligible_matches=row[0],
        archive_1_evaluated=row[1],
        archive_2_evaluated=row[2],
        score_list_evaluated=row[3],
        score_list_hits=row[4],
    )


@router.get("/api/analysis-validation", response_model=AnalysisValidation)
async def analysis_validation() -> AnalysisValidation:
    """Evaluate frozen pre-kickoff selections only after a confirmed FT result."""
    async with get_session() as session:
        recorded, resolved = (await session.execute(
            _VALIDATION_COUNTS, {"rule_version": RULE_VERSION},
        )).one()
        rows = (await session.execute(
            _VALIDATION_MARKETS, {"rule_version": RULE_VERSION},
        )).all()
    return AnalysisValidation(
        rule_version=RULE_VERSION,
        recorded=recorded,
        resolved=resolved,
        markets=[MarketValidation(archive=row[0], market=row[1], evaluated=row[2], hits=row[3])
                 for row in rows],
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
