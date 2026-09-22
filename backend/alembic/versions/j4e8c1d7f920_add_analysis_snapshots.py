"""Store immutable pre-kickoff market picks.

Revision ID: j4e8c1d7f920
Revises: i3b76d4e9a10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "j4e8c1d7f920"
down_revision: Union[str, None] = "i3b76d4e9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_snapshots",
        sa.Column("match_id", sa.String(length=20), primary_key=True),
        sa.Column("rule_version", sa.String(length=32), primary_key=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kickoff_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("league_name", sa.String(length=100), nullable=False),
        sa.Column("picks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("analysis_snapshots")
