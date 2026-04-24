"""add_pattern_columns

matches tablosuna 6 yeni JSONB kolon ekler — pattern B/C sonuçlarını saklayarak
runtime hesabını ortadan kaldırır. Sub-saniye analiz hedefi.

Revision ID: b7e4a2d8c901
Revises: a3f9e2b1c4d5
Create Date: 2026-04-25 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'b7e4a2d8c901'
down_revision: Union[str, None] = 'a3f9e2b1c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PATTERN_COLUMNS = (
    "pattern_ht_b",
    "pattern_ht_c",
    "pattern_h2_b",
    "pattern_h2_c",
    "pattern_ft_b",
    "pattern_ft_c",
)


def upgrade() -> None:
    for col in PATTERN_COLUMNS:
        op.add_column("matches", sa.Column(col, JSONB, nullable=True))


def downgrade() -> None:
    for col in PATTERN_COLUMNS:
        op.drop_column("matches", col)
