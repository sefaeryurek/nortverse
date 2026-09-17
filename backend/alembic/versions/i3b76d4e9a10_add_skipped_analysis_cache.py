"""Cache recently skipped analyses to avoid repeated scraping.

Revision ID: i3b76d4e9a10
Revises: h8c91e7a2b04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "i3b76d4e9a10"
down_revision: Union[str, None] = "h8c91e7a2b04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skipped_analysis",
        sa.Column("match_id", sa.String(length=20), primary_key=True),
        sa.Column("home_team", sa.String(length=100), nullable=False),
        sa.Column("away_team", sa.String(length=100), nullable=False),
        sa.Column("league_code", sa.String(length=50), nullable=True),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("skipped_analysis")
