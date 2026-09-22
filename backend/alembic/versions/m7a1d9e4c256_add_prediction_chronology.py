"""Make result knowledge and prediction capture chronology explicit.

Revision ID: m7a1d9e4c256
Revises: k5f8c4b2a613
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "m7a1d9e4c256"
down_revision: Union[str, None] = "k5f8c4b2a613"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("result_first_fetched_at", sa.DateTime(timezone=True)))
    op.execute("""
        UPDATE matches
        SET result_first_fetched_at = result_fetched_at
        WHERE result_fetched_at IS NOT NULL
          AND actual_ft_home IS NOT NULL AND actual_ft_away IS NOT NULL
    """)
    op.add_column("analysis_snapshots", sa.Column("analyzed_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE analysis_snapshots SET analyzed_at = captured_at WHERE analyzed_at IS NULL")
    op.alter_column("analysis_snapshots", "analyzed_at", nullable=False)
    op.create_check_constraint(
        "ck_analysis_snapshots_chronology", "analysis_snapshots",
        "analyzed_at <= captured_at AND captured_at < kickoff_time",
    )
    # Older stored patterns had no historical as-of cutoff; recompute lazily.
    op.execute("UPDATE matches SET pattern_computed_at = NULL WHERE pattern_computed_at IS NOT NULL")


def downgrade() -> None:
    op.drop_constraint("ck_analysis_snapshots_chronology", "analysis_snapshots", type_="check")
    op.drop_column("analysis_snapshots", "analyzed_at")
    op.drop_column("matches", "result_first_fetched_at")
