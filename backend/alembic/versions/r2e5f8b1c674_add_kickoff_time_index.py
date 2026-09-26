"""kickoff_time index — birçok hot query buna bağlı.

Revision ID: r2e5f8b1c674
Revises: q1d4a7b9e563
"""

from alembic import op

revision = "r2e5f8b1c674"
down_revision = "q1d4a7b9e563"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_matches_kickoff_time", "matches", ["kickoff_time"])


def downgrade() -> None:
    op.drop_index("ix_matches_kickoff_time", table_name="matches")
