"""Sık kullanılan sorgu kolonlarına index — league_code, actual_ft_home.

deleted_at index'i Sprint 8.9'da manuel SQL ile eklenmişti, burada atlanır.

Revision ID: s3f6a9c2d785
Revises: r2e5f8b1c674
"""

from alembic import op

revision = "s3f6a9c2d785"
down_revision = "r2e5f8b1c674"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_matches_league_code", "matches", ["league_code"])
    op.create_index("ix_matches_actual_ft_home", "matches", ["actual_ft_home"])


def downgrade() -> None:
    op.drop_index("ix_matches_actual_ft_home", table_name="matches")
    op.drop_index("ix_matches_league_code", table_name="matches")
