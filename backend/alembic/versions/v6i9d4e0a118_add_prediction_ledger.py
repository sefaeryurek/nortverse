"""add_prediction_ledger

Tahmin defteri (Sprint 88 Faz 1): değişmez İY gözlemi, gösterilen tahminlerin
değişmez defteri, tuttu/tutmadı çözümleri ve ayrı backtest tabloları.
DDL, app/db/models.py'den üretilip burada donduruldu.

Revision ID: v6i9d4e0a118
Revises: u5h8c3d9f907
Create Date: 2026-10-18

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'v6i9d4e0a118'
down_revision: Union[str, None] = 'u5h8c3d9f907'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_IMMUTABLE_TABLES = ("match_ht_observations", "prediction_ledger", "prediction_resolutions")
_NEW_TABLES = (
    "prediction_backtest", "backtest_runs", "prediction_resolutions",
    "prediction_ledger", "match_ht_observations",
)

_DDL = (
    """
    CREATE TABLE match_ht_observations (
    	id BIGSERIAL NOT NULL,
    	match_id VARCHAR(20) NOT NULL,
    	kickoff_time TIMESTAMP WITH TIME ZONE NOT NULL,
    	ht_home INTEGER NOT NULL,
    	ht_away INTEGER NOT NULL,
    	phase VARCHAR(12) NOT NULL,
    	observed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    	ingested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    	source VARCHAR(50) NOT NULL,
    	source_revision VARCHAR(128) NOT NULL,
    	PRIMARY KEY (id),
    	CONSTRAINT fk_match_ht_observations_match FOREIGN KEY(match_id) REFERENCES matches (match_id) ON DELETE RESTRICT,
    	CONSTRAINT uq_match_ht_observations_source_revision UNIQUE (match_id, source, source_revision),
    	CONSTRAINT ck_match_ht_observations_chronology CHECK (observed_at > kickoff_time),
    	CONSTRAINT ck_match_ht_observations_score_range CHECK (ht_home BETWEEN 0 AND 30 AND ht_away BETWEEN 0 AND 30),
    	CONSTRAINT ck_match_ht_observations_phase CHECK (phase IN ('ht_break', 'second_half', 'final')),
    	CONSTRAINT ck_match_ht_observations_source CHECK (length(trim(source)) > 0 AND length(trim(source_revision)) > 0)
    )
    """,
    """
    CREATE INDEX ix_match_ht_observations_match_ingested ON match_ht_observations (match_id, ingested_at, id)
    """,
    """
    CREATE TABLE prediction_ledger (
    	id BIGSERIAL NOT NULL,
    	origin VARCHAR(16) DEFAULT 'realtime' NOT NULL,
    	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    	ht_observation_id BIGINT,
    	source VARCHAR(16) NOT NULL,
    	rule_version VARCHAR(32) NOT NULL,
    	pattern_hash VARCHAR(48),
    	match_id VARCHAR(20) NOT NULL,
    	league_name VARCHAR(100) NOT NULL,
    	kickoff_time TIMESTAMP WITH TIME ZONE NOT NULL,
    	as_of TIMESTAMP WITH TIME ZONE NOT NULL,
    	period VARCHAR(2) NOT NULL,
    	market VARCHAR(24) NOT NULL,
    	selection VARCHAR(16) NOT NULL,
    	archive VARCHAR(8),
    	agreement_set VARCHAR(16),
    	agreement INTEGER,
    	prob_shown_bp INTEGER NOT NULL,
    	prob_raw_bp INTEGER,
    	prob_cal_bp INTEGER,
    	baseline_selection VARCHAR(16),
    	baseline_prob_bp INTEGER,
    	confidence_tier VARCHAR(12),
    	sample_n INTEGER,
    	informational BOOLEAN DEFAULT 'false' NOT NULL,
    	ht_home INTEGER,
    	ht_away INTEGER,
    	details JSONB DEFAULT '{}' NOT NULL,
    	PRIMARY KEY (id),
    	CONSTRAINT ck_prediction_ledger_source CHECK (source IN ('live_ht', 'top_pick', 'market_summary')),
    	CONSTRAINT ck_prediction_ledger_period CHECK (period IN ('ht', 'h2', 'ft')),
    	CONSTRAINT ck_prediction_ledger_market CHECK (market ~ '^[a-z0-9_]+$'),
    	CONSTRAINT ck_prediction_ledger_selection CHECK (length(trim(selection)) > 0),
    	CONSTRAINT ck_prediction_ledger_archive CHECK (archive IS NULL OR archive IN ('a1', 'a2', 'a3')),
    	CONSTRAINT ck_prediction_ledger_agreement CHECK (agreement IS NULL OR agreement BETWEEN 0 AND 3),
    	CONSTRAINT ck_prediction_ledger_prob_range CHECK (prob_shown_bp BETWEEN 0 AND 10000 AND (prob_raw_bp IS NULL OR prob_raw_bp BETWEEN 0 AND 10000) AND (prob_cal_bp IS NULL OR prob_cal_bp BETWEEN 0 AND 10000) AND (baseline_prob_bp IS NULL OR baseline_prob_bp BETWEEN 0 AND 10000)),
    	CONSTRAINT ck_prediction_ledger_tier CHECK (confidence_tier IS NULL OR confidence_tier IN ('high', 'medium', 'low', 'insufficient')),
    	CONSTRAINT ck_prediction_ledger_sample CHECK (sample_n IS NULL OR sample_n > 0),
    	CONSTRAINT ck_prediction_ledger_ht_pair CHECK ((ht_home IS NULL) = (ht_away IS NULL)),
    	CONSTRAINT fk_prediction_ledger_match FOREIGN KEY(match_id) REFERENCES matches (match_id) ON DELETE RESTRICT,
    	CONSTRAINT fk_prediction_ledger_ht_observation FOREIGN KEY(ht_observation_id) REFERENCES match_ht_observations (id) ON DELETE RESTRICT,
    	CONSTRAINT uq_prediction_ledger_decision UNIQUE NULLS NOT DISTINCT (source, rule_version, match_id, period, market, archive),
    	CONSTRAINT ck_prediction_ledger_origin CHECK (origin IN ('realtime', 'backfill_v3')),
    	CONSTRAINT ck_prediction_ledger_recorded_after_as_of CHECK (as_of <= recorded_at),
    	CONSTRAINT ck_prediction_ledger_chronology CHECK ((source = 'live_ht' AND as_of > kickoff_time AND ht_home IS NOT NULL AND ht_observation_id IS NOT NULL) OR (source IN ('top_pick', 'market_summary') AND as_of < kickoff_time AND (origin = 'backfill_v3' OR recorded_at < kickoff_time)))
    )
    """,
    """
    CREATE INDEX ix_prediction_ledger_match ON prediction_ledger (match_id)
    """,
    """
    CREATE INDEX ix_prediction_ledger_source_kickoff ON prediction_ledger (source, rule_version, kickoff_time)
    """,
    """
    CREATE TABLE prediction_resolutions (
    	id BIGSERIAL NOT NULL,
    	ledger_id BIGINT NOT NULL,
    	outcome VARCHAR(8) NOT NULL,
    	ft_home INTEGER,
    	ft_away INTEGER,
    	ht_home INTEGER,
    	ht_away INTEGER,
    	resolver_version VARCHAR(16) NOT NULL,
    	resolved_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    	PRIMARY KEY (id),
    	CONSTRAINT fk_prediction_resolutions_ledger FOREIGN KEY(ledger_id) REFERENCES prediction_ledger (id) ON DELETE RESTRICT,
    	CONSTRAINT uq_prediction_resolutions_state UNIQUE NULLS NOT DISTINCT (ledger_id, resolver_version, ft_home, ft_away, ht_home, ht_away, outcome),
    	CONSTRAINT ck_prediction_resolutions_outcome CHECK (outcome IN ('hit', 'miss', 'void'))
    )
    """,
    """
    CREATE INDEX ix_prediction_resolutions_ledger ON prediction_resolutions (ledger_id, id)
    """,
    """
    CREATE TABLE backtest_runs (
    	id BIGSERIAL NOT NULL,
    	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    	strategy VARCHAR(16) NOT NULL,
    	rule_version VARCHAR(32) NOT NULL,
    	params JSONB DEFAULT '{}' NOT NULL,
    	date_from TIMESTAMP WITH TIME ZONE NOT NULL,
    	date_to TIMESTAMP WITH TIME ZONE NOT NULL,
    	train_until TIMESTAMP WITH TIME ZONE,
    	git_sha VARCHAR(40),
    	notes VARCHAR(500),
    	PRIMARY KEY (id)
    )
    """,
    """
    CREATE TABLE prediction_backtest (
    	id BIGSERIAL NOT NULL,
    	run_id BIGINT NOT NULL,
    	outcome VARCHAR(8),
    	ft_home INTEGER,
    	ft_away INTEGER,
    	source VARCHAR(16) NOT NULL,
    	rule_version VARCHAR(32) NOT NULL,
    	pattern_hash VARCHAR(48),
    	match_id VARCHAR(20) NOT NULL,
    	league_name VARCHAR(100) NOT NULL,
    	kickoff_time TIMESTAMP WITH TIME ZONE NOT NULL,
    	as_of TIMESTAMP WITH TIME ZONE NOT NULL,
    	period VARCHAR(2) NOT NULL,
    	market VARCHAR(24) NOT NULL,
    	selection VARCHAR(16) NOT NULL,
    	archive VARCHAR(8),
    	agreement_set VARCHAR(16),
    	agreement INTEGER,
    	prob_shown_bp INTEGER NOT NULL,
    	prob_raw_bp INTEGER,
    	prob_cal_bp INTEGER,
    	baseline_selection VARCHAR(16),
    	baseline_prob_bp INTEGER,
    	confidence_tier VARCHAR(12),
    	sample_n INTEGER,
    	informational BOOLEAN DEFAULT 'false' NOT NULL,
    	ht_home INTEGER,
    	ht_away INTEGER,
    	details JSONB DEFAULT '{}' NOT NULL,
    	PRIMARY KEY (id),
    	CONSTRAINT ck_prediction_backtest_source CHECK (source IN ('live_ht', 'top_pick', 'market_summary')),
    	CONSTRAINT ck_prediction_backtest_period CHECK (period IN ('ht', 'h2', 'ft')),
    	CONSTRAINT ck_prediction_backtest_market CHECK (market ~ '^[a-z0-9_]+$'),
    	CONSTRAINT ck_prediction_backtest_selection CHECK (length(trim(selection)) > 0),
    	CONSTRAINT ck_prediction_backtest_archive CHECK (archive IS NULL OR archive IN ('a1', 'a2', 'a3')),
    	CONSTRAINT ck_prediction_backtest_agreement CHECK (agreement IS NULL OR agreement BETWEEN 0 AND 3),
    	CONSTRAINT ck_prediction_backtest_prob_range CHECK (prob_shown_bp BETWEEN 0 AND 10000 AND (prob_raw_bp IS NULL OR prob_raw_bp BETWEEN 0 AND 10000) AND (prob_cal_bp IS NULL OR prob_cal_bp BETWEEN 0 AND 10000) AND (baseline_prob_bp IS NULL OR baseline_prob_bp BETWEEN 0 AND 10000)),
    	CONSTRAINT ck_prediction_backtest_tier CHECK (confidence_tier IS NULL OR confidence_tier IN ('high', 'medium', 'low', 'insufficient')),
    	CONSTRAINT ck_prediction_backtest_sample CHECK (sample_n IS NULL OR sample_n > 0),
    	CONSTRAINT ck_prediction_backtest_ht_pair CHECK ((ht_home IS NULL) = (ht_away IS NULL)),
    	CONSTRAINT fk_prediction_backtest_run FOREIGN KEY(run_id) REFERENCES backtest_runs (id) ON DELETE CASCADE,
    	CONSTRAINT uq_prediction_backtest_decision UNIQUE NULLS NOT DISTINCT (run_id, match_id, period, market, archive),
    	CONSTRAINT ck_prediction_backtest_outcome CHECK (outcome IS NULL OR outcome IN ('hit', 'miss', 'void'))
    )
    """,
    """
    CREATE INDEX ix_prediction_backtest_run ON prediction_backtest (run_id, kickoff_time)
    """
)

_RESOLVED_VIEW = """
    CREATE VIEW prediction_ledger_resolved AS
    SELECT l.*, r.outcome, r.ft_home AS res_ft_home, r.ft_away AS res_ft_away,
           r.ht_home AS res_ht_home, r.ht_away AS res_ht_away,
           r.resolver_version, r.resolved_at
    FROM prediction_ledger l
    LEFT JOIN LATERAL (
        SELECT * FROM prediction_resolutions pr
        WHERE pr.ledger_id = l.id ORDER BY pr.id DESC LIMIT 1
    ) r ON true
"""

# v3 dondurulmuş tahminleri deftere kopyala (yalnız model seçimi olanlar).
_BACKFILL_V3 = """
    INSERT INTO prediction_ledger (
        source, origin, rule_version, match_id, league_name, kickoff_time, as_of,
        period, market, selection, prob_shown_bp, prob_raw_bp,
        baseline_selection, baseline_prob_bp, sample_n, informational, details
    )
    SELECT 'top_pick', 'backfill_v3', m.rule_version, m.match_id, s.league_name,
           s.kickoff_time, s.captured_at, 'ft',
           CASE m.market WHEN 'over_25' THEN 'ou_25' WHEN 'btts' THEN 'kg' ELSE 'result' END,
           m.model_selection, m.model_score_bp, m.model_score_bp,
           m.baseline_selection, m.baseline_score_bp, m.model_sample_size,
           m.market IN ('over_25', 'btts'),
           jsonb_build_object('model_source', m.model_source, 'captured_at', s.captured_at)
    FROM analysis_snapshot_markets m
    JOIN analysis_snapshots s ON s.match_id = m.match_id AND s.rule_version = m.rule_version
    WHERE m.model_selection IS NOT NULL
"""


def upgrade() -> None:
    for statement in _DDL:
        op.execute(statement)
    op.execute("""
        CREATE FUNCTION nortverse_force_recorded_at()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.recorded_at := clock_timestamp();
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE FUNCTION nortverse_force_resolved_at()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.resolved_at := clock_timestamp();
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_match_ht_observations_ingested_at
        BEFORE INSERT ON match_ht_observations
        FOR EACH ROW EXECUTE FUNCTION nortverse_force_result_ingested_at()
    """)
    op.execute("""
        CREATE TRIGGER trg_prediction_ledger_recorded_at
        BEFORE INSERT ON prediction_ledger
        FOR EACH ROW EXECUTE FUNCTION nortverse_force_recorded_at()
    """)
    op.execute("""
        CREATE TRIGGER trg_prediction_resolutions_resolved_at
        BEFORE INSERT ON prediction_resolutions
        FOR EACH ROW EXECUTE FUNCTION nortverse_force_resolved_at()
    """)
    for table in _IMMUTABLE_TABLES:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_immutable
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION nortverse_reject_immutable_change()
        """)
        op.execute(f"""
            CREATE TRIGGER trg_{table}_truncate_immutable
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION nortverse_reject_immutable_change()
        """)
    op.execute(_RESOLVED_VIEW)
    op.execute(_BACKFILL_V3)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM prediction_ledger WHERE origin <> 'backfill_v3' LIMIT 1)
               OR EXISTS (SELECT 1 FROM prediction_resolutions LIMIT 1)
               OR EXISTS (SELECT 1 FROM match_ht_observations LIMIT 1) THEN
                RAISE EXCEPTION 'Refusing destructive downgrade: prediction ledger contains data';
            END IF;
        END;
        $$
    """)
    op.execute("DROP VIEW prediction_ledger_resolved")
    for table in _IMMUTABLE_TABLES:
        op.execute(f"DROP TRIGGER trg_{table}_truncate_immutable ON {table}")
        op.execute(f"DROP TRIGGER trg_{table}_immutable ON {table}")
    for table in _NEW_TABLES:
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP FUNCTION nortverse_force_resolved_at()")
    op.execute("DROP FUNCTION nortverse_force_recorded_at()")
