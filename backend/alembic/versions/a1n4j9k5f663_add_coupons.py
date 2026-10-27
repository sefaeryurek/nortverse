"""Kupondaş: kuponlar, kupon maçları (oran dondurulur) ve sonuçları — hepsi değişmez (Sprint 93)

Revision ID: a1n4j9k5f663
Revises: z0m3h8i4e552
Create Date: 2026-10-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1n4j9k5f663"
down_revision: Union[str, None] = "z0m3h8i4e552"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("coupons", "coupon_legs", "coupon_leg_results")


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.Column("note", sa.String(200), nullable=True),
    )
    op.create_index("ix_coupons_created", "coupons", ["created_at"])
    op.create_table(
        "coupon_legs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("coupon_id", sa.BigInteger(), sa.ForeignKey("coupons.id"), nullable=False),
        sa.Column("match_id", sa.String(20), sa.ForeignKey("matches.match_id"), nullable=False),
        sa.Column("home_team", sa.String(100), nullable=False),
        sa.Column("away_team", sa.String(100), nullable=False),
        sa.Column("league_name", sa.String(100), nullable=True),
        sa.Column("kickoff_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period", sa.String(2), nullable=False),
        sa.Column("market", sa.String(10), nullable=False),
        sa.Column("selection", sa.String(10), nullable=False),
        sa.Column("line", sa.Float(), nullable=True),
        sa.Column("odds", sa.Float(), nullable=False),
        sa.Column("odds_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("live_minute", sa.String(10), nullable=True),
        sa.Column("live_score", sa.String(10), nullable=True),
        sa.CheckConstraint("period IN ('ft', 'ht')", name="ck_coupon_legs_period"),
        sa.CheckConstraint("market IN ('result', 'dc', 'ou')", name="ck_coupon_legs_market"),
        sa.CheckConstraint("odds > 1.0 AND odds < 1000", name="ck_coupon_legs_odds"),
        sa.UniqueConstraint("coupon_id", "match_id", "period", "market", name="uq_coupon_legs_pick"),
    )
    op.create_index("ix_coupon_legs_coupon", "coupon_legs", ["coupon_id"])
    op.create_index("ix_coupon_legs_match", "coupon_legs", ["match_id"])
    op.create_table(
        "coupon_leg_results",
        sa.Column("leg_id", sa.BigInteger(), sa.ForeignKey("coupon_legs.id"), primary_key=True),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column("return_factor", sa.Float(), nullable=False),
        sa.Column("score", sa.String(10), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("outcome IN ('hit', 'miss', 'push', 'half_win', 'half_loss', 'void')",
                           name="ck_coupon_leg_results_outcome"),
    )
    for table in _TABLES:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION nortverse_reject_immutable_change()
        """)
        op.execute(f"""
            CREATE TRIGGER trg_{table}_truncate_immutable BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION nortverse_reject_immutable_change()
        """)


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_truncate_immutable ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable ON {table}")
    op.drop_table("coupon_leg_results")
    op.drop_index("ix_coupon_legs_match", table_name="coupon_legs")
    op.drop_index("ix_coupon_legs_coupon", table_name="coupon_legs")
    op.drop_table("coupon_legs")
    op.drop_index("ix_coupons_created", table_name="coupons")
    op.drop_table("coupons")
