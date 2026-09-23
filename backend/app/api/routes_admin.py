"""Yönetim endpoint'leri: health, quality, correlations."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter
from sqlalchemy import case, func, or_, select, text

from app.analysis.correlation import compute_poisson_correlations
from app.analysis.league_filter import CUP_KEYWORDS, is_supported_league
from app.analysis.snapshots import BASELINE_VERSION, RULE_VERSION
from app.analysis.score_snapshots import SCORE_RULE_VERSION
from app.api.schemas import AnalysisEvidence, AnalysisValidationV3, DataQuality, HealthResponse, MarketValidationV3, ScoreValidation
from app.api.services import analysis_cache, bg_queue
from app.db.connection import get_session
from app.db.models import FixtureCache, Match

log = logging.getLogger(__name__)
router = APIRouter()

_corr_cache: dict[str, float] | None = None

_V3_MARKET_AGGREGATE = text("""
    WITH latest_result AS (
        SELECT match_id, ft_home, ft_away
        FROM (
            SELECT match_id, ft_home, ft_away,
                   ROW_NUMBER() OVER (
                       PARTITION BY match_id
                       ORDER BY ingested_at DESC, id DESC
                   ) AS rn
            FROM match_final_result_observations
        ) sub
        WHERE rn = 1
    ),
    market_with_outcome AS (
        SELECT
            mk.market,
            mk.model_selection,
            mk.model_score_bp,
            mk.baseline_selection,
            mk.abstain_reason,
            r.ft_home,
            r.ft_away,
            CASE
                WHEN mk.model_selection IS NULL THEN NULL
                WHEN r.ft_home IS NULL THEN NULL
                WHEN mk.market = 'result' THEN
                    (mk.model_selection = '1' AND r.ft_home > r.ft_away)
                    OR (mk.model_selection = 'X' AND r.ft_home = r.ft_away)
                    OR (mk.model_selection = '2' AND r.ft_home < r.ft_away)
                WHEN mk.market = 'over_25' THEN
                    (mk.model_selection = 'over') =
                    (r.ft_home + r.ft_away > 2)
                WHEN mk.market = 'btts' THEN
                    (mk.model_selection = 'yes') =
                    (r.ft_home > 0 AND r.ft_away > 0)
            END AS model_hit,
            CASE
                WHEN mk.baseline_selection IS NULL THEN NULL
                WHEN r.ft_home IS NULL THEN NULL
                WHEN mk.market = 'result' THEN
                    (mk.baseline_selection = '1' AND r.ft_home > r.ft_away)
                    OR (mk.baseline_selection = 'X' AND r.ft_home = r.ft_away)
                    OR (mk.baseline_selection = '2' AND r.ft_home < r.ft_away)
                WHEN mk.market = 'over_25' THEN
                    (mk.baseline_selection = 'over') =
                    (r.ft_home + r.ft_away > 2)
                WHEN mk.market = 'btts' THEN
                    (mk.baseline_selection = 'yes') =
                    (r.ft_home > 0 AND r.ft_away > 0)
            END AS baseline_hit
        FROM analysis_snapshot_markets mk
        JOIN analysis_snapshots s
            ON s.match_id = mk.match_id AND s.rule_version = mk.rule_version
        LEFT JOIN latest_result r
            ON r.match_id = mk.match_id
        WHERE mk.rule_version = :rule_version
          AND s.analyzed_at <= s.captured_at
          AND s.captured_at < s.kickoff_time
    )
    SELECT
        market,
        COUNT(*) AS opportunities,
        COUNT(*) FILTER (WHERE model_selection IS NOT NULL) AS issued,
        COUNT(*) FILTER (WHERE abstain_reason IS NOT NULL) AS abstained,
        COUNT(*) FILTER (WHERE model_selection IS NOT NULL
                         AND ft_home IS NOT NULL) AS resolved_issued,
        COUNT(*) FILTER (WHERE model_hit IS NOT NULL
                         AND baseline_hit IS NOT NULL) AS paired,
        COUNT(*) FILTER (WHERE model_hit AND baseline_hit) AS both_hit,
        COUNT(*) FILTER (WHERE model_hit AND NOT baseline_hit) AS model_only,
        COUNT(*) FILTER (WHERE NOT model_hit AND baseline_hit) AS baseline_only,
        COUNT(*) FILTER (WHERE NOT model_hit AND NOT baseline_hit) AS neither,
        COUNT(*) FILTER (WHERE model_hit) AS model_hits,
        AVG(model_score_bp / 100.0)
            FILTER (WHERE model_selection IS NOT NULL
                    AND ft_home IS NOT NULL) AS avg_freq,
        AVG(POWER(model_score_bp / 10000.0
                  - CASE WHEN model_hit THEN 1.0 ELSE 0.0 END, 2))
            FILTER (WHERE model_selection IS NOT NULL
                    AND ft_home IS NOT NULL) AS brier
    FROM market_with_outcome
    GROUP BY market
    ORDER BY market
""")

_V3_SNAPSHOT_COUNT = text("""
    SELECT count(*)
    FROM analysis_snapshots
    WHERE rule_version = :rule_version
""")

_BRIER_NOTE = (
    "selected_event_brier sadece modelin seçtiği event için hesaplanır; "
    "result pazarı için bu tam multiclass Brier değildir."
)


def wilson_ci(
    successes: int, trials: int, z: float = 1.96,
) -> tuple[float, float] | None:
    if trials <= 0:
        return None
    p = successes / trials
    z2 = z * z
    denom = 1 + z2 / trials
    center = p + z2 / (2 * trials)
    spread = z * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials))
    return (
        max(0.0, (center - spread) / denom),
        min(1.0, (center + spread) / denom),
    )

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


def paired_coverage_interval(model_only: int, baseline_only: int, paired: int) -> tuple[float, float, float] | None:
    """Distribution-free 95% interval for paired coverage difference."""
    if paired <= 0:
        return None
    difference = 100.0 * (model_only - baseline_only) / paired
    # Paired difference is bounded in [-1, 1] (range width 2).
    half_width = 100.0 * math.sqrt(2.0 * math.log(40.0) / paired)
    return difference, max(-100.0, difference - half_width), min(100.0, difference + half_width)


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
            ).where(*eligible, *league_filter)
        )).one()
    return AnalysisEvidence(
        eligible_matches=row[0],
        archive_1_evaluated=row[1],
        archive_2_evaluated=row[2],
        score_list_evaluated=row[3],
        score_list_hits=row[4],
    )


@router.get("/api/analysis-validation", response_model=AnalysisValidationV3)
async def analysis_validation() -> AnalysisValidationV3:
    """Evaluate frozen pre-kickoff selections using immutable observation ledger."""
    params = {"rule_version": RULE_VERSION}
    async with get_session() as session:
        total_snapshots = (await session.execute(_V3_SNAPSHOT_COUNT, params)).scalar() or 0
        rows = (await session.execute(_V3_MARKET_AGGREGATE, params)).all()

    markets: list[MarketValidationV3] = []
    for row in rows:
        (market, opportunities, issued, abstained, resolved_issued,
         paired, both_hit, model_only, baseline_only, neither,
         model_hits, avg_freq, brier) = row

        if resolved_issued < 30:
            tier = "cok_erken"
        elif resolved_issued < 100:
            tier = "on_bulgu"
        else:
            tier = "tam"

        cov_ci = wilson_ci(resolved_issued, opportunities)
        model_hits_paired = both_hit + model_only
        baseline_hits_paired = both_hit + baseline_only
        model_ci = wilson_ci(model_hits_paired, paired)
        base_ci = wilson_ci(baseline_hits_paired, paired)

        m_rate = model_hits_paired / paired if paired > 0 else None
        b_rate = baseline_hits_paired / paired if paired > 0 else None
        obs_rate = model_hits / resolved_issued if resolved_issued > 0 else None
        avg_f = float(avg_freq) if avg_freq is not None else None
        cal_gap = (avg_f - obs_rate * 100) if avg_f is not None and obs_rate is not None else None

        markets.append(MarketValidationV3(
            market=market,
            opportunities=opportunities,
            issued=issued,
            abstained=abstained,
            resolved_issued=resolved_issued,
            coverage=round(resolved_issued / opportunities, 4) if opportunities > 0 else None,
            coverage_ci_low=round(cov_ci[0], 4) if cov_ci else None,
            coverage_ci_high=round(cov_ci[1], 4) if cov_ci else None,
            paired=paired,
            both_hit=both_hit,
            model_only=model_only,
            baseline_only=baseline_only,
            neither=neither,
            model_hit_rate=round(m_rate, 4) if m_rate is not None else None,
            model_hit_rate_ci_low=round(model_ci[0], 4) if model_ci else None,
            model_hit_rate_ci_high=round(model_ci[1], 4) if model_ci else None,
            baseline_hit_rate=round(b_rate, 4) if b_rate is not None else None,
            baseline_hit_rate_ci_low=round(base_ci[0], 4) if base_ci else None,
            baseline_hit_rate_ci_high=round(base_ci[1], 4) if base_ci else None,
            paired_difference=round(
                (model_only - baseline_only) / paired, 4,
            ) if paired > 0 else None,
            avg_published_frequency=round(avg_f, 2) if avg_f is not None else None,
            observed_hit_rate=round(obs_rate * 100, 2) if obs_rate is not None else None,
            calibration_gap=round(cal_gap, 2) if cal_gap is not None else None,
            selected_event_brier=round(float(brier), 4) if brier is not None else None,
            display_tier=tier,
        ))

    return AnalysisValidationV3(
        rule_version=RULE_VERSION,
        baseline_version=BASELINE_VERSION,
        total_snapshots=total_snapshots,
        markets=markets,
        brier_note=_BRIER_NOTE,
    )


@router.get("/api/score-validation", response_model=ScoreValidation)
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
