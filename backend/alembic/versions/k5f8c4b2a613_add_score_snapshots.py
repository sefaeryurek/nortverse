"""Freeze pre-kickoff score shortlists and chronological baselines.

Revision ID: k5f8c4b2a613
Revises: j4e8c1d7f920
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "k5f8c4b2a613"
down_revision: Union[str, None] = "j4e8c1d7f920"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "score_snapshots",
        sa.Column("match_id", sa.String(length=20), primary_key=True),
        sa.Column("rule_version", sa.String(length=32), primary_key=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kickoff_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("league_name", sa.String(length=100), nullable=False),
        sa.Column("model_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("baseline_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("score_snapshots")
