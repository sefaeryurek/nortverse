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
    live_home: Optional[int] = None
    live_away: Optional[int] = None
    score_checked_at: Optional[str] = None
    status: str
    result: Optional[str] = None
    kg_var: Optional[bool] = None
    over_25: Optional[bool] = None
    katman_a_covered: Optional[bool] = None
