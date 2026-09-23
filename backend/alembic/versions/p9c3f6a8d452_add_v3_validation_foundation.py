"""Add normalized v3 prediction and append-only result observation storage.

Revision ID: p9c3f6a8d452
Revises: n8b2e5f7a341
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "p9c3f6a8d452"
down_revision: Union[str, None] = "n8b2e5f7a341"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "analysis_snapshots",
        sa.Column("baseline_version", sa.String(length=32), nullable=True),
    )
    op.create_check_constraint(
        "ck_analysis_snapshots_v3_baseline_version", "analysis_snapshots",
        "rule_version <> 'ft-display-v3' OR baseline_version IS NOT NULL",
    )
    op.create_table(
        "analysis_snapshot_markets",
        sa.Column("match_id", sa.String(length=20), nullable=False),
        sa.Column("rule_version", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("model_selection", sa.String(length=16), nullable=True),
        sa.Column("model_score_bp", sa.Integer(), nullable=True),
        sa.Column("model_sample_size", sa.Integer(), nullable=True),
        sa.Column("model_source", sa.String(length=50), nullable=True),
        sa.Column("baseline_selection", sa.String(length=16), nullable=True),
        sa.Column("baseline_score_bp", sa.Integer(), nullable=True),
        sa.Column("baseline_sample_size", sa.Integer(), nullable=True),
        sa.Column("baseline_scope", sa.String(length=50), nullable=True),
        sa.Column("abstain_reason", sa.String(length=100), nullable=True),
        sa.CheckConstraint(
            "market IN ('result', 'over_25', 'btts')",
            name="ck_analysis_snapshot_markets_market",
        ),
        sa.CheckConstraint(
            "model_selection IS NULL OR "
            "(market = 'result' AND model_selection IN ('1', 'X', '2')) OR "
            "(market = 'over_25' AND model_selection IN ('under', 'over')) OR "
            "(market = 'btts' AND model_selection IN ('yes', 'no'))",
            name="ck_analysis_snapshot_markets_model_selection",
        ),
        sa.CheckConstraint(
            "baseline_selection IS NULL OR "
            "(market = 'result' AND baseline_selection IN ('1', 'X', '2')) OR "
            "(market = 'over_25' AND baseline_selection IN ('under', 'over')) OR "
            "(market = 'btts' AND baseline_selection IN ('yes', 'no'))",
            name="ck_analysis_snapshot_markets_baseline_selection",
        ),
        sa.CheckConstraint(
            "model_score_bp IS NULL OR model_score_bp BETWEEN 0 AND 10000",
            name="ck_analysis_snapshot_markets_model_score_range",
        ),
        sa.CheckConstraint(
            "baseline_score_bp IS NULL OR baseline_score_bp BETWEEN 0 AND 10000",
            name="ck_analysis_snapshot_markets_baseline_score_range",
        ),
        sa.CheckConstraint(
            "model_sample_size IS NULL OR model_sample_size > 0",
            name="ck_analysis_snapshot_markets_model_sample_size",
        ),
        sa.CheckConstraint(
            "baseline_sample_size IS NULL OR baseline_sample_size > 0",
            name="ck_analysis_snapshot_markets_baseline_sample_size",
        ),
        sa.CheckConstraint(
            "((model_selection IS NULL AND model_score_bp IS NULL "
            "AND model_sample_size IS NULL AND model_source IS NULL "
            "AND abstain_reason IS NOT NULL AND length(trim(abstain_reason)) > 0) "
            "OR (model_selection IS NOT NULL AND model_score_bp IS NOT NULL "
            "AND model_sample_size IS NOT NULL AND model_source IS NOT NULL "
            "AND length(trim(model_source)) > 0 AND abstain_reason IS NULL))",
            name="ck_analysis_snapshot_markets_model_bundle",
        ),
        sa.CheckConstraint(
            "((baseline_selection IS NULL AND baseline_score_bp IS NULL "
            "AND baseline_sample_size IS NULL AND baseline_scope IS NULL) "
            "OR (baseline_selection IS NOT NULL AND baseline_score_bp IS NOT NULL "
            "AND baseline_sample_size IS NOT NULL AND baseline_scope IS NOT NULL "
            "AND length(trim(baseline_scope)) > 0))",
            name="ck_analysis_snapshot_markets_baseline_bundle",
        ),
        sa.ForeignKeyConstraint(
            ["match_id", "rule_version"],
            ["analysis_snapshots.match_id", "analysis_snapshots.rule_version"],
            name="fk_analysis_snapshot_markets_snapshot",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "match_id", "rule_version", "market",
            name="pk_analysis_snapshot_markets",
        ),
    )
    op.create_table(
        "match_final_result_observations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.String(length=20), nullable=False),
        sa.Column("kickoff_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ft_home", sa.Integer(), nullable=False),
        sa.Column("ft_away", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_revision", sa.String(length=128), nullable=False),
        sa.CheckConstraint(
            "observed_at > kickoff_time",
            name="ck_match_final_result_observations_chronology",
        ),
        sa.CheckConstraint(
            "ft_home BETWEEN 0 AND 30 AND ft_away BETWEEN 0 AND 30",
            name="ck_match_final_result_observations_score_range",
        ),
        sa.CheckConstraint(
            "length(trim(source)) > 0 AND length(trim(source_revision)) > 0",
            name="ck_match_final_result_observations_source",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_final_result_observations"),
        sa.ForeignKeyConstraint(
            ["match_id"], ["matches.match_id"],
            name="fk_match_final_result_observations_match", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "match_id", "source", "source_revision",
            name="uq_match_final_result_observations_source_revision",
        ),
    )
    op.create_index(
        "ix_match_final_result_observations_match_ingested",
        "match_final_result_observations",
        ["match_id", "ingested_at", "id"],
    )
    op.execute("""
        CREATE FUNCTION nortverse_reject_immutable_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION USING MESSAGE = TG_TABLE_NAME || ' is append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE FUNCTION nortverse_force_result_ingested_at()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.ingested_at := clock_timestamp();
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_match_final_result_observations_ingested_at
        BEFORE INSERT ON match_final_result_observations
        FOR EACH ROW EXECUTE FUNCTION nortverse_force_result_ingested_at()
    """)
    for table in (
        "analysis_snapshots", "analysis_snapshot_markets",
        "match_final_result_observations",
    ):
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


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM analysis_snapshot_markets LIMIT 1)
               OR EXISTS (SELECT 1 FROM match_final_result_observations LIMIT 1)
               OR EXISTS (
                   SELECT 1 FROM analysis_snapshots
                   WHERE rule_version = 'ft-display-v3'
                      OR baseline_version IS NOT NULL
                   LIMIT 1
               ) THEN
                RAISE EXCEPTION 'Refusing destructive downgrade: v3 audit tables contain data';
            END IF;
        END;
        $$
    """)
    for table in (
        "analysis_snapshots", "analysis_snapshot_markets",
        "match_final_result_observations",
    ):
        op.execute(f"DROP TRIGGER trg_{table}_truncate_immutable ON {table}")
        op.execute(f"DROP TRIGGER trg_{table}_immutable ON {table}")
    op.execute("""
        DROP TRIGGER trg_match_final_result_observations_ingested_at
        ON match_final_result_observations
    """)
    op.execute("DROP FUNCTION nortverse_force_result_ingested_at()")
    op.execute("DROP FUNCTION nortverse_reject_immutable_change()")
    op.drop_index(
        "ix_match_final_result_observations_match_ingested",
        table_name="match_final_result_observations",
    )
    op.drop_table("match_final_result_observations")
    op.drop_table("analysis_snapshot_markets")
    op.drop_constraint(
        "ck_analysis_snapshots_v3_baseline_version",
        "analysis_snapshots", type_="check",
    )
    op.drop_column("analysis_snapshots", "baseline_version")
