"""add_trends_column

matches tablosuna `trends` JSONB kolonu ekler — form/H2H trend bloğu burada saklanır.
Pattern saklamada olduğu gibi runtime hesabı yerine DB'den okur.

Revision ID: f5c8d2a1b394
Revises: b7e4a2d8c901
Create Date: 2026-05-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'f5c8d2a1b394'
down_revision: Union[str, None] = 'b7e4a2d8c901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("trends", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "trends")
