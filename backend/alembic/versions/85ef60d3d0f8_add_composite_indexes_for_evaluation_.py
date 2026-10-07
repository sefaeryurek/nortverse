"""add_composite_indexes_for_evaluation_and_pattern_d

Revision ID: 85ef60d3d0f8
Revises: 0101cf818042
Create Date: 2026-10-07 22:50:08.983737

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '85ef60d3d0f8'
down_revision: Union[str, None] = '0101cf818042'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_matches_eval_lookup',
        'matches',
        ['kickoff_time'],
        unique=False,
        postgresql_where='deleted_at IS NULL AND actual_ft_home IS NOT NULL',
    )
    op.create_index(
        'ix_matches_pattern_d_candidates',
        'matches',
        ['analyzed_at'],
        unique=False,
        postgresql_where='ft_all_ratios IS NOT NULL AND deleted_at IS NULL',
    )


def downgrade() -> None:
    op.drop_index('ix_matches_pattern_d_candidates', table_name='matches')
    op.drop_index('ix_matches_eval_lookup', table_name='matches')
