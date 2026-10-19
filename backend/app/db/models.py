"""SQLAlchemy ORM modelleri."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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
    # none_as_null: "eşleşme yok" SQL NULL olarak yazılır (JSON 'null' değil).
    pattern_ht_b: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    pattern_ht_c: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    pattern_h2_b: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    pattern_h2_c: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    pattern_ft_b: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    pattern_ft_c: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    pattern_ht_d: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    pattern_h2_d: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    pattern_ft_d: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    # Ayar parmak izi — ayar değişince sadece ilgili aile yeniden hesaplanır.
    pattern_b_hash: Mapped[str | None] = mapped_column(String(16))
    pattern_c_hash: Mapped[str | None] = mapped_column(String(16))
    pattern_d_hash: Mapped[str | None] = mapped_column(String(16))
    # Maç öncesi takım gücü beklentisi (live_poisson modeli, as_of ≤ kickoff) — A3 en yakın maç uzayı
    team_lambda_home: Mapped[float | None] = mapped_column(Float)
    team_lambda_away: Mapped[float | None] = mapped_column(Float)
    team_lambda_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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


class MatchHtObservation(Base):
    """Değişmez İY skoru gözlemi — canlı tahminin İY anında dondurulduğunun kanıtı."""

    __tablename__ = "match_ht_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["match_id"], ["matches.match_id"],
            name="fk_match_ht_observations_match", ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "match_id", "source", "source_revision",
            name="uq_match_ht_observations_source_revision",
        ),
        CheckConstraint("observed_at > kickoff_time", name="ck_match_ht_observations_chronology"),
        CheckConstraint(
            "ht_home BETWEEN 0 AND 30 AND ht_away BETWEEN 0 AND 30",
            name="ck_match_ht_observations_score_range",
        ),
        CheckConstraint(
            "phase IN ('ht_break', 'second_half', 'final')", name="ck_match_ht_observations_phase",
        ),
        CheckConstraint(
            "length(trim(source)) > 0 AND length(trim(source_revision)) > 0",
            name="ck_match_ht_observations_source",
        ),
        Index("ix_match_ht_observations_match_ingested", "match_id", "ingested_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(String(20), nullable=False)
    kickoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ht_home: Mapped[int] = mapped_column(Integer, nullable=False)
    ht_away: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(12), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_revision: Mapped[str] = mapped_column(String(128), nullable=False)


# Defter ve backtest tabloları aynı tahmin kolonlarını paylaşır.
_LEDGER_SOURCES = "('live_ht', 'top_pick', 'market_summary')"


def _prediction_columns_checks(prefix: str) -> tuple:
    return (
        CheckConstraint(f"source IN {_LEDGER_SOURCES}", name=f"ck_{prefix}_source"),
        CheckConstraint("period IN ('ht', 'h2', 'ft')", name=f"ck_{prefix}_period"),
        CheckConstraint("market ~ '^[a-z0-9_]+$'", name=f"ck_{prefix}_market"),
        CheckConstraint("length(trim(selection)) > 0", name=f"ck_{prefix}_selection"),
        CheckConstraint(
            "archive IS NULL OR archive IN ('a1', 'a2', 'a3')", name=f"ck_{prefix}_archive",
        ),
        CheckConstraint(
            "agreement IS NULL OR agreement BETWEEN 0 AND 3", name=f"ck_{prefix}_agreement",
        ),
        CheckConstraint(
            "prob_shown_bp BETWEEN 0 AND 10000"
            " AND (prob_raw_bp IS NULL OR prob_raw_bp BETWEEN 0 AND 10000)"
            " AND (prob_cal_bp IS NULL OR prob_cal_bp BETWEEN 0 AND 10000)"
            " AND (baseline_prob_bp IS NULL OR baseline_prob_bp BETWEEN 0 AND 10000)",
            name=f"ck_{prefix}_prob_range",
        ),
        CheckConstraint(
            "confidence_tier IS NULL OR confidence_tier IN ('high', 'medium', 'low', 'insufficient')",
            name=f"ck_{prefix}_tier",
        ),
        CheckConstraint("sample_n IS NULL OR sample_n > 0", name=f"ck_{prefix}_sample"),
        CheckConstraint(
            "(ht_home IS NULL) = (ht_away IS NULL)", name=f"ck_{prefix}_ht_pair",
        ),
    )


class _PredictionColumns:
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    pattern_hash: Mapped[str | None] = mapped_column(String(48))
    match_id: Mapped[str] = mapped_column(String(20), nullable=False)
    league_name: Mapped[str] = mapped_column(String(100), nullable=False)
    kickoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period: Mapped[str] = mapped_column(String(2), nullable=False)
    market: Mapped[str] = mapped_column(String(24), nullable=False)
    selection: Mapped[str] = mapped_column(String(16), nullable=False)
    archive: Mapped[str | None] = mapped_column(String(8))
    agreement_set: Mapped[str | None] = mapped_column(String(16))
    agreement: Mapped[int | None] = mapped_column(Integer)
    prob_shown_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    prob_raw_bp: Mapped[int | None] = mapped_column(Integer)
    prob_cal_bp: Mapped[int | None] = mapped_column(Integer)
    baseline_selection: Mapped[str | None] = mapped_column(String(16))
    baseline_prob_bp: Mapped[int | None] = mapped_column(Integer)
    confidence_tier: Mapped[str | None] = mapped_column(String(12))
    sample_n: Mapped[int | None] = mapped_column(Integer)
    informational: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    ht_home: Mapped[int | None] = mapped_column(Integer)
    ht_away: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


class PredictionLedger(_PredictionColumns, Base):
    """Kullanıcıya gerçekten gösterilen tahminlerin değişmez defteri (ilk kayıt kazanır)."""

    __tablename__ = "prediction_ledger"
    __table_args__ = (
        *_prediction_columns_checks("prediction_ledger"),
        ForeignKeyConstraint(
            ["match_id"], ["matches.match_id"],
            name="fk_prediction_ledger_match", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ht_observation_id"], ["match_ht_observations.id"],
            name="fk_prediction_ledger_ht_observation", ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "source", "rule_version", "match_id", "period", "market", "archive",
            name="uq_prediction_ledger_decision", postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "origin IN ('realtime', 'backfill_v3')", name="ck_prediction_ledger_origin",
        ),
        CheckConstraint("as_of <= recorded_at", name="ck_prediction_ledger_recorded_after_as_of"),
        CheckConstraint(
            "(source = 'live_ht' AND as_of > kickoff_time AND ht_home IS NOT NULL"
            " AND ht_observation_id IS NOT NULL)"
            " OR (source IN ('top_pick', 'market_summary') AND as_of < kickoff_time"
            " AND (origin = 'backfill_v3' OR recorded_at < kickoff_time))",
            name="ck_prediction_ledger_chronology",
        ),
        Index("ix_prediction_ledger_source_kickoff", "source", "rule_version", "kickoff_time"),
        Index("ix_prediction_ledger_match", "match_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    origin: Mapped[str] = mapped_column(String(16), nullable=False, server_default="realtime")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    ht_observation_id: Mapped[int | None] = mapped_column(BigInteger)


class PredictionResolution(Base):
    """Defter satırının tuttu/tutmadı çözümü — skor düzeltilirse yeni satır eklenir."""

    __tablename__ = "prediction_resolutions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["ledger_id"], ["prediction_ledger.id"],
            name="fk_prediction_resolutions_ledger", ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "ledger_id", "resolver_version", "ft_home", "ft_away", "ht_home", "ht_away", "outcome",
            name="uq_prediction_resolutions_state", postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "outcome IN ('hit', 'miss', 'void')", name="ck_prediction_resolutions_outcome",
        ),
        Index("ix_prediction_resolutions_ledger", "ledger_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ledger_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    ft_home: Mapped[int | None] = mapped_column(Integer)
    ft_away: Mapped[int | None] = mapped_column(Integer)
    ht_home: Mapped[int | None] = mapped_column(Integer)
    ht_away: Mapped[int | None] = mapped_column(Integer)
    resolver_version: Mapped[str] = mapped_column(String(16), nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class BacktestRun(Base):
    """Bir backtest koşusu — 'bugünkü algoritma o gün ne derdi' simülasyonu."""

    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    strategy: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    date_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    train_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    git_sha: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(String(500))


class PredictionBacktest(_PredictionColumns, Base):
    """Backtest tahminleri — gerçek defterle şema seviyesinde karışmaz, yeniden üretilebilir."""

    __tablename__ = "prediction_backtest"
    __table_args__ = (
        *_prediction_columns_checks("prediction_backtest"),
        ForeignKeyConstraint(
            ["run_id"], ["backtest_runs.id"],
            name="fk_prediction_backtest_run", ondelete="CASCADE",
        ),
        UniqueConstraint(
            "run_id", "match_id", "period", "market", "archive",
            name="uq_prediction_backtest_decision", postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('hit', 'miss', 'void')",
            name="ck_prediction_backtest_outcome",
        ),
        Index("ix_prediction_backtest_run", "run_id", "kickoff_time"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(8))
    ft_home: Mapped[int | None] = mapped_column(Integer)
    ft_away: Mapped[int | None] = mapped_column(Integer)


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
