"""add_fixture_cache_table

Revision ID: a3f9e2b1c4d5
Revises: c1b1b4cd333b
Create Date: 2026-04-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'a3f9e2b1c4d5'
down_revision: Union[str, None] = 'c1b1b4cd333b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'fixture_cache',
        sa.Column('date', sa.String(10), primary_key=True),
        sa.Column('matches_json', JSONB, nullable=False),
        sa.Column('cached_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('fixture_cache')
