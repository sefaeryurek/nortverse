"""add_league_name_index

Revision ID: t4g7b2c8e896
Revises: 85ef60d3d0f8
Create Date: 2026-10-11

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 't4g7b2c8e896'
down_revision: Union[str, None] = '85ef60d3d0f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_matches_league_name',
        'matches',
        ['league_name'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_matches_league_name', table_name='matches')
