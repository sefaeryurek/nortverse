"""Oran geçmişi önbelleği: match_odds (Sprint 93 — İY değer kuralı + kupondaş)

Revision ID: y9l2g7h3d441
Revises: x8k1f6g2c330
Create Date: 2026-10-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "y9l2g7h3d441"
down_revision: Union[str, None] = "x8k1f6g2c330"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "match_odds",
        sa.Column("match_id", sa.String(20), primary_key=True),
        sa.Column("scope", sa.String(2), primary_key=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("history", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.match_id"], ondelete="CASCADE"),
        sa.CheckConstraint("scope IN ('ht', 'ft')", name="ck_match_odds_scope"),
    )


def downgrade() -> None:
    op.drop_table("match_odds")
