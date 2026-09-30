"""API response/request modelleri."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.analysis.pattern_stats import PatternResult
from app.analysis.trends import TrendsData


class DataQuality(BaseModel):
    """Sprint 8.9 — DB sağlığı/veri kalitesi göstergesi."""
    total_matches: int = 0
    active_matches: int = 0
    soft_deleted: int = 0
    non_league_active: int = 0
    missing_pattern: int = 0  # Hesaplama durumu henüz bilinmeyen kayıtlar.
    missing_trends: int = 0
    missing_actual_score: int = 0
    quality_score: float = 100.0


class AnalysisEvidence(BaseModel):
    """Coverage of saved, pre-kickoff full-time analysis snapshots."""
    eligible_matches: int
    archive_1_evaluated: int
    archive_2_evaluated: int
    score_list_evaluated: int
    score_list_hits: int
    minimum_for_rate: int = 100


class MarketValidationV3(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    market: str

    opportunities: int
    issued: int
    abstained: int
    resolved_issued: int

    coverage: float | None = None
    coverage_ci_low: float | None = None
    coverage_ci_high: float | None = None

    paired: int
    both_hit: int
    model_only: int
    baseline_only: int
    neither: int

    model_hit_rate: float | None = None
    model_hit_rate_ci_low: float | None = None
    model_hit_rate_ci_high: float | None = None
    baseline_hit_rate: float | None = None
    baseline_hit_rate_ci_low: float | None = None
    baseline_hit_rate_ci_high: float | None = None
    paired_difference: float | None = None

    avg_published_frequency: float | None = None
    observed_hit_rate: float | None = None
    calibration_gap: float | None = None

    selected_event_brier: float | None = None

    display_tier: str


class AnalysisValidationV3(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    rule_version: str
    baseline_version: str
    total_snapshots: int
    markets: list[MarketValidationV3]
    brier_note: str


class ScoreValidation(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    rule_version: str
    recorded: int
    resolved: int
    evaluated: int
    paired: int
    list_hits: int
    paired_model_hits: int
    baseline_hits: int
    both_hit: int
    model_only: int
    baseline_only: int
    neither: int
    coverage_difference_pp: Optional[float] = None
    difference_ci_low_pp: Optional[float] = None
    difference_ci_high_pp: Optional[float] = None
    minimum_for_rate: int = 100


class HealthResponse(BaseModel):
    """Hafif sağlık göstergesi — UptimeRobot her 5dk ping atıyor.

    Sprint 8.10: data_quality buradan KALDIRILDI (tüm matches taraması egress
    aşımına yol açıyordu). Detaylı kalite raporu için /api/admin/quality.
    """
    status: str
    version: str = __import__("app").__version__
    db_ok: bool
    last_pipeline_at: Optional[str] = None
    last_fixture_cached_at: Optional[str] = None
    bg_queue_size: int = 0
    cached_analyses: int = 0


class FixtureMatchOut(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    league_code: str
    league_name: Optional[str]
    kickoff_time: Optional[str]
    status: str = "scheduled"
    live_home: Optional[int] = None
    live_away: Optional[int] = None
    live_minute: Optional[str] = None
    score_checked_at: Optional[str] = None
    has_prediction: bool = False


class PeriodOut(BaseModel):
    scores_1: list[str]
    scores_x: list[str]
    scores_2: list[str]


class RecommendationOut(BaseModel):
    recommendation_id: str
    archive: str
    market: str
    selection: str
    frequency_pct: float
    match_count: int
    archive_1_frequency_pct: Optional[float] = None
    archive_1_match_count: Optional[int] = None
    archive_2_frequency_pct: Optional[float] = None
    archive_2_match_count: Optional[int] = None


class AnalyzeResponse(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    league_code: str
    season: str
    ht: PeriodOut
    half2: PeriodOut
    ft: PeriodOut
    ht_b: Optional[PatternResult] = None
    ht_c: Optional[PatternResult] = None
    h2_b: Optional[PatternResult] = None
    h2_c: Optional[PatternResult] = None
    ft_b: Optional[PatternResult] = None
    ft_c: Optional[PatternResult] = None
    trends: Optional[TrendsData] = None
    recommendation_rule_version: str = "ft-display-v3"
    ft_recommendations: list[RecommendationOut] = Field(default_factory=list)
    skipped: bool = False
    skip_reason: Optional[str] = None


class MatchSummary(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    league_code: Optional[str]
    season: Optional[str]
    actual_ft_home: Optional[int]
    actual_ft_away: Optional[int]
    actual_ht_home: Optional[int]
    actual_ht_away: Optional[int]
    ft_scores_1: Optional[list]
    ft_scores_x: Optional[list]
    ft_scores_2: Optional[list]


# ─── Günlük Değerlendirme (Sprint 37) ────────────────────────────────────────

class PatternEvaluation(BaseModel):
    match_count: int
    result_pick: str
    result_pct: float
    result_hit: bool
    result_margin: float = 0.0
    is_confident: bool = False
    over_25_pick: str
    over_25_pct: float
    over_25_hit: bool
    btts_pick: str
    btts_pct: float
    btts_hit: bool


class MatchEvaluation(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    league_code: Optional[str] = None
    league_name: Optional[str] = None
    kickoff_time: Optional[str] = None
    actual_ft: str
    actual_ht: Optional[str] = None
    result: str
    over_25: bool
    btts: bool
    pattern_b: Optional[PatternEvaluation] = None
    pattern_c: Optional[PatternEvaluation] = None
    score_list: list[str] = Field(default_factory=list)
    score_list_hit: bool = False


class EvaluationSummary(BaseModel):
    total_matches: int = 0
    evaluated: int = 0
    result_hit: int = 0
    result_hit_pct: float = 0.0
    over_25_hit: int = 0
    over_25_hit_pct: float = 0.0
    btts_hit: int = 0
    btts_hit_pct: float = 0.0
    score_list_hit: int = 0
    score_list_hit_pct: float = 0.0
    evaluated_c: int = 0
    c_result_hit: int = 0
    c_result_hit_pct: float = 0.0
    c_over_25_hit: int = 0
    c_over_25_hit_pct: float = 0.0
    c_btts_hit: int = 0
    c_btts_hit_pct: float = 0.0
    confident_evaluated: int = 0
    confident_result_hit: int = 0
    confident_result_hit_pct: float = 0.0


class DailyEvaluation(BaseModel):
    date: str
    summary: EvaluationSummary
    matches: list[MatchEvaluation] = Field(default_factory=list)


class ResultOut(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    league_code: Optional[str]
    league_name: Optional[str]
    kickoff_time: Optional[str]
    actual_ft_home: Optional[int] = None
    actual_ft_away: Optional[int] = None
    actual_ht_home: Optional[int] = None
    actual_ht_away: Optional[int] = None
    score_checked_at: Optional[str] = None
    status: str
    result: Optional[str] = None
    kg_var: Optional[bool] = None
    over_25: Optional[bool] = None
    katman_a_covered: Optional[bool] = None
