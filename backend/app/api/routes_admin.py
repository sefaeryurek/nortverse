"""Yönetim endpoint'leri: health, quality, correlations."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import case, func, or_, select, text

from app.scraper.browser import playwright_stats
from app.scraper.odds import odds_stats
from app.config import ISTANBUL_TZ
from app.analysis.correlation import compute_poisson_correlations
from app.analysis.league_filter import CUP_KEYWORDS
from app.analysis.repair import compute_quality_score
from app.analysis.stats_utils import paired_coverage_interval
from app.analysis.score_snapshots import SCORE_RULE_VERSION
from app.api.schemas import AnalysisEvidence, DataQuality, HealthResponse, ScoreValidation
from app.api.services import analysis_cache, bg_queue
from app.db.connection import get_session
from app.db.models import FixtureCache, Match

log = logging.getLogger(__name__)
router = APIRouter()

_ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "")


async def _require_admin(request: Request) -> None:
    """Yönetici uçları: geçerli `X-Admin-Key` (sabit zamanlı karşılaştırma) ya da yönetici hesabıyla oturum
    (Sprint 94 E8: anahtar tanımlı değilken giriş yapmış her kullanıcı erişebiliyordu)."""
    import hmac

    from app.auth import is_admin_request

    token = request.headers.get("X-Admin-Key", "")
    if _ADMIN_KEY and token and hmac.compare_digest(token.encode(), _ADMIN_KEY.encode()):
        return
    if not is_admin_request(request):
        raise HTTPException(403, "Yetkisiz erişim")


_corr_cache: dict[str, float] | None = None

_SCORE_VALIDATION = text("""
    WITH eligible AS (
        SELECT s.model_scores, s.baseline_scores,
               jsonb_exists(s.model_scores, m.actual_ft_home::text || '-' || m.actual_ft_away::text) AS model_hit,
               jsonb_exists(s.baseline_scores, m.actual_ft_home::text || '-' || m.actual_ft_away::text) AS baseline_hit
        FROM score_snapshots s
        JOIN matches m ON m.match_id = s.match_id
        WHERE s.rule_version = :rule_version
          AND m.deleted_at IS NULL
          AND m.actual_ft_home IS NOT NULL AND m.actual_ft_away IS NOT NULL
          AND COALESCE(m.result_first_fetched_at, m.result_fetched_at) > s.kickoff_time
          AND s.analyzed_at <= s.captured_at
          AND s.captured_at < s.kickoff_time
    )
    SELECT
        (SELECT count(*) FROM score_snapshots WHERE rule_version = :rule_version),
        count(*),
        count(*) FILTER (WHERE jsonb_array_length(model_scores) > 0),
        count(*) FILTER (WHERE jsonb_array_length(model_scores) > 0 AND baseline_scores IS NOT NULL),
        count(*) FILTER (WHERE jsonb_array_length(model_scores) > 0 AND model_hit),
        count(*) FILTER (WHERE jsonb_array_length(model_scores) > 0 AND baseline_scores IS NOT NULL AND model_hit),
        count(*) FILTER (WHERE jsonb_array_length(model_scores) > 0 AND baseline_scores IS NOT NULL AND baseline_hit),
        count(*) FILTER (WHERE jsonb_array_length(model_scores) > 0 AND baseline_scores IS NOT NULL AND model_hit AND baseline_hit),
        count(*) FILTER (WHERE jsonb_array_length(model_scores) > 0 AND baseline_scores IS NOT NULL AND model_hit AND NOT baseline_hit),
        count(*) FILTER (WHERE jsonb_array_length(model_scores) > 0 AND baseline_scores IS NOT NULL AND NOT model_hit AND baseline_hit),
        count(*) FILTER (WHERE jsonb_array_length(model_scores) > 0 AND baseline_scores IS NOT NULL AND NOT model_hit AND NOT baseline_hit)
    FROM eligible
""")


@router.api_route("/api/health", methods=["GET", "HEAD"], response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Sistem sağlık kontrolü — denetleyici ve sağlık betiği sadece 200'e bakar.

    Sprint 94 E8: girişsiz istekte sadece durum (ok/degraded) döner; pipeline saati, kuyruk ve kazıyıcı sayaçları
    oturum ister.
    """
    db_ok = False
    last_pipeline: Optional[datetime] = None
    last_fixture_cached: Optional[datetime] = None

    try:
        async with get_session() as session:
            row = await session.execute(select(func.max(Match.analyzed_at)))
            last_pipeline = row.scalar_one_or_none()

            fc = await session.get(FixtureCache, datetime.now(ISTANBUL_TZ).date().isoformat())
            if fc:
                last_fixture_cached = fc.cached_at

            db_ok = True
    except Exception as exc:
        log.warning("Health check DB sorgusu başarısız: %s", exc)

    from app.auth import auth_required

    if auth_required() and getattr(request.state, "user", None) is None:
        from fastapi.responses import JSONResponse

        return JSONResponse({"status": "ok" if db_ok else "degraded", "db_ok": db_ok})
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db_ok=db_ok,
        last_pipeline_at=last_pipeline.isoformat() if last_pipeline else None,
        last_fixture_cached_at=last_fixture_cached.isoformat() if last_fixture_cached else None,
        bg_queue_size=bg_queue.qsize() if bg_queue else 0,
        cached_analyses=len(analysis_cache),
        scraper={"playwright": playwright_stats(), "odds": odds_stats()},
    )


@router.get("/api/analysis-evidence", response_model=AnalysisEvidence)
async def analysis_evidence() -> AnalysisEvidence:
    """Count only analyses saved before kickoff and matches with a final score.

    JSONB null is distinct from SQL NULL, so count actual pattern objects.
    This reports coverage; it does not claim a calibrated hit rate.
    """
    eligible = (
        Match.deleted_at.is_(None), Match.model_only.is_(False),
        Match.actual_ft_home.is_not(None),
        Match.actual_ft_away.is_not(None),
        func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at).is_not(None),
        Match.kickoff_time.is_not(None),
        Match.analyzed_at.is_not(None),
        Match.pattern_computed_at.is_not(None),
        Match.analyzed_at < Match.kickoff_time,
        Match.pattern_computed_at < Match.kickoff_time,
        func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at) > Match.kickoff_time,
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
                func.count(Match.id).filter(func.jsonb_typeof(Match.pattern_ft_d) == "object"),
            ).where(*eligible, *league_filter)
        )).one()
    return AnalysisEvidence(
        eligible_matches=row[0],
        archive_1_evaluated=row[1],
        archive_2_evaluated=row[2],
        archive_3_evaluated=row[5],
        score_list_evaluated=row[3],
        score_list_hits=row[4],
    )


@router.get("/api/score-validation", response_model=ScoreValidation, dependencies=[Depends(_require_admin)])
async def score_validation() -> ScoreValidation:
    """Compare frozen score lists with equal-length prior-score baselines."""
    async with get_session() as session:
        row = (await session.execute(
            _SCORE_VALIDATION, {"rule_version": SCORE_RULE_VERSION},
        )).one()
    interval = paired_coverage_interval(row[8], row[9], row[3])
    return ScoreValidation(
        rule_version=SCORE_RULE_VERSION,
        recorded=row[0], resolved=row[1], evaluated=row[2], paired=row[3],
        list_hits=row[4], paired_model_hits=row[5], baseline_hits=row[6],
        both_hit=row[7], model_only=row[8], baseline_only=row[9], neither=row[10],
        coverage_difference_pp=round(interval[0], 2) if interval else None,
        difference_ci_low_pp=round(interval[1], 2) if interval else None,
        difference_ci_high_pp=round(interval[2], 2) if interval else None,
    )


@router.get("/api/admin/quality", response_model=DataQuality, dependencies=[Depends(_require_admin)])
async def admin_quality() -> DataQuality:
    """Detaylı veri kalitesi raporu."""
    async with get_session() as session:
        total = (await session.execute(select(func.count(Match.id)))).scalar() or 0
        active = (await session.execute(
            select(func.count(Match.id)).where(Match.deleted_at.is_(None), Match.model_only.is_(False))
        )).scalar() or 0
        soft_deleted = total - active

        non_league_q = select(func.count(Match.id)).where(
            Match.deleted_at.is_(None), Match.model_only.is_(False),
            Match.league_name.is_(None),
        )
        non_league = (await session.execute(non_league_q)).scalar() or 0

        missing_pattern = (await session.execute(
            select(func.count(Match.id)).where(
                Match.deleted_at.is_(None), Match.model_only.is_(False), Match.pattern_computed_at.is_(None),
            )
        )).scalar() or 0
        missing_trends = (await session.execute(
            select(func.count(Match.id)).where(
                Match.deleted_at.is_(None), Match.model_only.is_(False), Match.trends.is_(None)
            )
        )).scalar() or 0
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=130)
        missing_actual = (await session.execute(
            select(func.count(Match.id)).where(
                Match.deleted_at.is_(None), Match.model_only.is_(False),
                Match.kickoff_time < cutoff,
                or_(Match.actual_ft_home.is_(None), Match.actual_ft_away.is_(None)),
            )
        )).scalar() or 0

    score = compute_quality_score(
        total=total, active=active,
        non_league=non_league,
        missing_pattern=missing_pattern,
        missing_actual=missing_actual,
        missing_trends=missing_trends,
    )

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
