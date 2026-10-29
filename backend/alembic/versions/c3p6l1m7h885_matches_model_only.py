"""Yalnız model maç satırı (Sprint 94 P1, K15): matches.model_only

H2H'ta 5'ten az lig maçı olan takip maçları eskiden hiç kaydedilmiyordu; takım gücü (v5) ve canlı Poisson
modeli H2H'a ihtiyaç duymadığı halde kural onları da kesiyordu (ana ligde maçların ~%28'i). Artık bu maçlar
`model_only = true` satırıyla yazılır: takım, lig, saat, skor ve λ var; Katman A ve A1/A2/A3 boş. Defter
kayıtları (sadece gölge sürümler) için `matches` satırı şart (yabancı anahtar).

Ana liglerin oranları değişmesin diye bu satırlar ortak havuzlara (COND, lig ortalaması, takım gücü eğitimi,
A3 adayları) ve ekran listelerine girmez — her sorgu `Match.model_only.is_(False)` ile süzer.

Revision ID: c3p6l1m7h885
Revises: b2o5k0l6g774
Create Date: 2026-10-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3p6l1m7h885"
down_revision: Union[str, None] = "b2o5k0l6g774"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("model_only", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_matches_model_only", "matches", ["model_only"], postgresql_where=sa.text("model_only"))


def downgrade() -> None:
    op.drop_index("ix_matches_model_only", table_name="matches")
    op.drop_column("matches", "model_only")
