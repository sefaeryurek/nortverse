"""Enforce score snapshot chronology in the database.

Revision ID: n8b2e5f7a341
Revises: m7a1d9e4c256
"""

from typing import Sequence, Union

from alembic import op


revision: str = "n8b2e5f7a341"
down_revision: Union[str, None] = "m7a1d9e4c256"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_score_snapshots_chronology", "score_snapshots",
        "analyzed_at <= captured_at AND captured_at < kickoff_time",
    )


def downgrade() -> None:
    op.drop_constraint("ck_score_snapshots_chronology", "score_snapshots", type_="check")
