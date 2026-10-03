"""add_ht_score_index

Revision ID: 0101cf818042
Revises: fcefb39a3642
Create Date: 2026-10-03 15:31:48.120802

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0101cf818042'
down_revision: Union[str, None] = 'fcefb39a3642'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_matches_ht_score",
        "matches",
        ["actual_ht_home", "actual_ht_away"],
        postgresql_where=sa.text("deleted_at IS NULL AND actual_ft_home IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_matches_ht_score", table_name="matches")
