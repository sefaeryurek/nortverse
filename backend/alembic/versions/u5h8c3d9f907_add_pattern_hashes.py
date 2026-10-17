"""add_pattern_hashes

Ayar parmak izi kolonları (pattern_b/c/d_hash) — ayar değişince sadece ilgili
aile yeniden hesaplanır. Ayrıca JSON 'null' pattern değerleri SQL NULL'a
çevrilir ve pattern_computed_at hesaplamada kullanılan as_of'a hizalanır.

Revision ID: u5h8c3d9f907
Revises: t4g7b2c8e896
Create Date: 2026-10-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'u5h8c3d9f907'
down_revision: Union[str, None] = 't4g7b2c8e896'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PATTERN_COLS = [f"pattern_{p}_{f}" for p in ("ht", "h2", "ft") for f in ("b", "c", "d")]


def upgrade() -> None:
    for family in ("b", "c", "d"):
        op.add_column("matches", sa.Column(f"pattern_{family}_hash", sa.String(16), nullable=True))
    for col in _PATTERN_COLS:
        op.execute(f"UPDATE matches SET {col} = NULL WHERE {col} = 'null'::jsonb")
    op.execute(
        "UPDATE matches SET pattern_computed_at = LEAST(analyzed_at, kickoff_time) "
        "WHERE pattern_computed_at IS NOT NULL AND analyzed_at IS NOT NULL AND kickoff_time IS NOT NULL"
    )


def downgrade() -> None:
    for family in ("b", "c", "d"):
        op.drop_column("matches", f"pattern_{family}_hash")
