"""Maç olayları: gol dakikaları + kırmızı kartlar (Sprint 93 — anlık maç modeli kalibrasyonu)

Revision ID: x8k1f6g2c330
Revises: w7j0e5f1b229
Create Date: 2026-10-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "x8k1f6g2c330"
down_revision: Union[str, None] = "w7j0e5f1b229"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # [{"minute": 27, "extra": 0, "side": "home", "kind": "goal|penalty|own_goal|red", "score": [2, 1]}, ...]
    op.add_column("matches", sa.Column("goal_events", postgresql.JSONB(none_as_null=True), nullable=True))
    op.add_column("matches", sa.Column("goal_events_fetched_at", sa.DateTime(timezone=True), nullable=True))
    # Olaylardan çıkan skor maçın kayıtlı sonucuyla uyuşuyor mu (uyuşmayan maç kalibrasyonda kullanılmaz)
    op.add_column("matches", sa.Column("goal_events_ok", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "goal_events_ok")
    op.drop_column("matches", "goal_events_fetched_at")
    op.drop_column("matches", "goal_events")
