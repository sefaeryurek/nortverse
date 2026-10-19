"""Maç öncesi takım gücü beklentileri (λ ev / λ dep) — A3 takım gücü uzayında en yakın maçlar (Sprint 91 Faz 4)

Revision ID: w7j0e5f1b229
Revises: v6i9d4e0a118
Create Date: 2026-10-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w7j0e5f1b229"
down_revision: Union[str, None] = "v6i9d4e0a118"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("team_lambda_home", sa.Float(), nullable=True))
    op.add_column("matches", sa.Column("team_lambda_away", sa.Float(), nullable=True))
    # Hangi andaki takım modeliyle hesaplandı (maç öncesi: as_of ≤ kickoff → sızıntısız)
    op.add_column("matches", sa.Column("team_lambda_as_of", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "team_lambda_as_of")
    op.drop_column("matches", "team_lambda_away")
    op.drop_column("matches", "team_lambda_home")
