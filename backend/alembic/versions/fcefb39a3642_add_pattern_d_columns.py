"""add_pattern_d_columns

Revision ID: fcefb39a3642
Revises: s3f6a9c2d785
Create Date: 2026-10-03 15:22:45.090704

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fcefb39a3642'
down_revision: Union[str, None] = 's3f6a9c2d785'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('matches', sa.Column('pattern_ht_d', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('matches', sa.Column('pattern_h2_d', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('matches', sa.Column('pattern_ft_d', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('matches', 'pattern_ft_d')
    op.drop_column('matches', 'pattern_h2_d')
    op.drop_column('matches', 'pattern_ht_d')
