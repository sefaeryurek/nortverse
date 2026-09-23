"""SQLAlchemy ORM modelleri."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    home_team: Mapped[str] = mapped_column(String(100), nullable=False)
    away_team: Mapped[str] = mapped_column(String(100), nullable=False)
    league_code: Mapped[str | None] = mapped_column(String(50))
    league_name: Mapped[str | None] = mapped_column(String(100))
    kickoff_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    season: Mapped[str | None] = mapped_column(String(10))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pattern_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Katman A — İlk Yarı
    ht_scores_1: Mapped[dict | None] = mapped_column(JSONB)
    ht_scores_x: Mapped[dict | None] = mapped_column(JSONB)
    ht_scores_2: Mapped[dict | None] = mapped_column(JSONB)
    ht_all_ratios: Mapped[dict | None] = mapped_column(JSONB)

    # Katman A — İkinci Yarı
    h2_scores_1: Mapped[dict | None] = mapped_column(JSONB)
    h2_scores_x: Mapped[dict | None] = mapped_column(JSONB)
    h2_scores_2: Mapped[dict | None] = mapped_column(JSONB)
    h2_all_ratios: Mapped[dict | None] = mapped_column(JSONB)

    # Katman A — Maç Sonu
    ft_scores_1: Mapped[dict | None] = mapped_column(JSONB)
    ft_scores_x: Mapped[dict | None] = mapped_column(JSONB)
    ft_scores_2: Mapped[dict | None] = mapped_column(JSONB)
    ft_all_ratios: Mapped[dict | None] = mapped_column(JSONB)

    # Pattern sonuçları (kaydedilmiş — sub-saniye analiz için)
    # exclude_match_id=match_id ile hesaplanmıştır, okurken ek filtre gerekmez
    pattern_ht_b: Mapped[dict | None] = mapped_column(JSONB)
    pattern_ht_c: Mapped[dict | None] = mapped_column(JSONB)
    pattern_h2_b: Mapped[dict | None] = mapped_column(JSONB)
    pattern_h2_c: Mapped[dict | None] = mapped_column(JSONB)
    pattern_ft_b: Mapped[dict | None] = mapped_column(JSONB)
    pattern_ft_c: Mapped[dict | None] = mapped_column(JSONB)

    # Form & H2H trendleri (Sprint 8.8) — TrendsData JSON
    trends: Mapped[dict | None] = mapped_column(JSONB)

    # Gerçek sonuç
    actual_ht_home: Mapped[int | None] = mapped_column(Integer)
    actual_ht_away: Mapped[int | None] = mapped_column(Integer)
    actual_h2_home: Mapped[int | None] = mapped_column(Integer)
    actual_h2_away: Mapped[int | None] = mapped_column(Integer)
    actual_ft_home: Mapped[int | None] = mapped_column(Integer)
    actual_ft_away: Mapped[int | None] = mapped_column(Integer)
    result_first_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Soft delete (Sprint 8.9) — kupa temizliği geri alınabilir
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_reason: Mapped[str | None] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Match {self.match_id}: {self.home_team} vs {self.away_team}>"


class AuditLog(Base):
    """Veri bütünlüğü değişiklik kaydı (Sprint 8.9).

    Tüm prune/silme/restore/recompute işlemleri burada saklanır.
    Production incident analizi ve geri alma için kritik.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    target_match_id: Mapped[str | None] = mapped_column(String(20))
    actor: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict | None] = mapped_column(JSONB)


class FixtureCache(Base):
    """Günlük bülten listesi cache tablosu.

    Playwright scrape sonucu burada saklanır. Server restart'larından etkilenmez.
    Geçmiş tarihler kalıcı, bugün/gelecek için 1 saatlik TTL uygulanır.
    """

    __tablename__ = "fixture_cache"

    date: Mapped[str] = mapped_column(String(10), primary_key=True)  # "YYYY-MM-DD"
    matches_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SkippedAnalysis(Base):
    """Recent filter result so an ineligible match is not scraped on every visit."""

    __tablename__ = "skipped_analysis"

    match_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    home_team: Mapped[str] = mapped_column(String(100), nullable=False)
    away_team: Mapped[str] = mapped_column(String(100), nullable=False)
    league_code: Mapped[str | None] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AnalysisSnapshot(Base):
    """First pre-kickoff FT picks for one fixed rule version; never updated."""

    __tablename__ = "analysis_snapshots"
    __table_args__ = (
        CheckConstraint(
            "rule_version <> 'ft-display-v3' OR baseline_version IS NOT NULL",
            name="ck_analysis_snapshots_v3_baseline_version",
        ),
    )

    match_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    rule_version: Mapped[str] = mapped_column(String(32), primary_key=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kickoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    league_name: Mapped[str] = mapped_column(String(100), nullable=False)
    picks: Mapped[list] = mapped_column(JSONB, nullable=False)
    baseline_version: Mapped[str | None] = mapped_column(String(32))


class AnalysisSnapshotMarket(Base):
    """Normalized model and baseline decision for one frozen market."""

    __tablename__ = "analysis_snapshot_markets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["match_id", "rule_version"],
            ["analysis_snapshots.match_id", "analysis_snapshots.rule_version"],
            name="fk_analysis_snapshot_markets_snapshot",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "market IN ('result', 'over_25', 'btts')",
            name="ck_analysis_snapshot_markets_market",
        ),
        CheckConstraint(
            "model_selection IS NULL OR "
            "(market = 'result' AND model_selection IN ('1', 'X', '2')) OR "
            "(market = 'over_25' AND model_selection IN ('under', 'over')) OR "
            "(market = 'btts' AND model_selection IN ('yes', 'no'))",
            name="ck_analysis_snapshot_markets_model_selection",
        ),
        CheckConstraint(
            "baseline_selection IS NULL OR "
            "(market = 'result' AND baseline_selection IN ('1', 'X', '2')) OR "
            "(market = 'over_25' AND baseline_selection IN ('under', 'over')) OR "
            "(market = 'btts' AND baseline_selection IN ('yes', 'no'))",
            name="ck_analysis_snapshot_markets_baseline_selection",
        ),
        CheckConstraint(
            "model_score_bp IS NULL OR model_score_bp BETWEEN 0 AND 10000",
            name="ck_analysis_snapshot_markets_model_score_range",
        ),
        CheckConstraint(
            "baseline_score_bp IS NULL OR baseline_score_bp BETWEEN 0 AND 10000",
            name="ck_analysis_snapshot_markets_baseline_score_range",
        ),
        CheckConstraint(
            "model_sample_size IS NULL OR model_sample_size > 0",
            name="ck_analysis_snapshot_markets_model_sample_size",
        ),
        CheckConstraint(
            "baseline_sample_size IS NULL OR baseline_sample_size > 0",
            name="ck_analysis_snapshot_markets_baseline_sample_size",
        ),
        CheckConstraint(
            "((model_selection IS NULL AND model_score_bp IS NULL "
            "AND model_sample_size IS NULL AND model_source IS NULL "
            "AND abstain_reason IS NOT NULL AND length(trim(abstain_reason)) > 0) "
            "OR (model_selection IS NOT NULL AND model_score_bp IS NOT NULL "
            "AND model_sample_size IS NOT NULL AND model_source IS NOT NULL "
            "AND length(trim(model_source)) > 0 AND abstain_reason IS NULL))",
            name="ck_analysis_snapshot_markets_model_bundle",
        ),
        CheckConstraint(
            "((baseline_selection IS NULL AND baseline_score_bp IS NULL "
            "AND baseline_sample_size IS NULL AND baseline_scope IS NULL) "
            "OR (baseline_selection IS NOT NULL AND baseline_score_bp IS NOT NULL "
            "AND baseline_sample_size IS NOT NULL AND baseline_scope IS NOT NULL "
            "AND length(trim(baseline_scope)) > 0))",
            name="ck_analysis_snapshot_markets_baseline_bundle",
        ),
    )

    match_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    rule_version: Mapped[str] = mapped_column(String(32), primary_key=True)
    market: Mapped[str] = mapped_column(String(16), primary_key=True)
    model_selection: Mapped[str | None] = mapped_column(String(16))
    model_score_bp: Mapped[int | None] = mapped_column(Integer)
    model_sample_size: Mapped[int | None] = mapped_column(Integer)
    model_source: Mapped[str | None] = mapped_column(String(50))
    baseline_selection: Mapped[str | None] = mapped_column(String(16))
    baseline_score_bp: Mapped[int | None] = mapped_column(Integer)
    baseline_sample_size: Mapped[int | None] = mapped_column(Integer)
    baseline_scope: Mapped[str | None] = mapped_column(String(50))
    abstain_reason: Mapped[str | None] = mapped_column(String(100))


class MatchFinalResultObservation(Base):
    """Immutable source revision of a final score observation."""

    __tablename__ = "match_final_result_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["match_id"], ["matches.match_id"],
            name="fk_match_final_result_observations_match",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "match_id", "source", "source_revision",
            name="uq_match_final_result_observations_source_revision",
        ),
        CheckConstraint(
            "observed_at > kickoff_time",
            name="ck_match_final_result_observations_chronology",
        ),
        CheckConstraint(
            "ft_home BETWEEN 0 AND 30 AND ft_away BETWEEN 0 AND 30",
            name="ck_match_final_result_observations_score_range",
        ),
        CheckConstraint(
            "length(trim(source)) > 0 AND length(trim(source_revision)) > 0",
            name="ck_match_final_result_observations_source",
        ),
        Index(
            "ix_match_final_result_observations_match_ingested",
            "match_id", "ingested_at", "id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(String(20), nullable=False)
    kickoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ft_home: Mapped[int] = mapped_column(Integer, nullable=False)
    ft_away: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_revision: Mapped[str] = mapped_column(String(128), nullable=False)


class ScoreSnapshot(Base):
    """Frozen pre-kickoff score shortlist and its equally sized baseline."""

    __tablename__ = "score_snapshots"

    match_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    rule_version: Mapped[str] = mapped_column(String(32), primary_key=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kickoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    league_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_scores: Mapped[list] = mapped_column(JSONB, nullable=False)
    baseline_scores: Mapped[list | None] = mapped_column(JSONB)
