"""Avrupa kupaları arşivi (Sprint 94 P4, K17 seçenek B): cup_results

UCL / UEL / UECL lig (grup) aşaması maçlarının İY ve 90 dakika skoru. Sadece canlı "aynı kupa + aynı İY skoru"
gölge kuralı (live-cup-cond-v1) okur; `matches` tablosuna girmediği için ana liglerin hiçbir havuzuna
(COND, lig ortalaması, takım gücü, arşivler) karışmaz. Eleme ve ön eleme turları alınmaz (uzatma/penaltı
skoru 90 dakikaya karışabilir; iki ayaklı eşleşmenin rövanşı farklı oynanır).

Revision ID: d4q7m2n8i996
Revises: c3p6l1m7h885
Create Date: 2026-11-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4q7m2n8i996"
down_revision: Union[str, None] = "c3p6l1m7h885"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cup_results",
        sa.Column("match_id", sa.String(20), primary_key=True),
        sa.Column("competition", sa.String(100), nullable=False),
        sa.Column("season", sa.String(10), nullable=False),
        sa.Column("round", sa.String(40), nullable=True),
        sa.Column("kickoff_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("home_team", sa.String(100), nullable=False),
        sa.Column("away_team", sa.String(100), nullable=False),
        sa.Column("ht_home", sa.SmallInteger(), nullable=False),
        sa.Column("ht_away", sa.SmallInteger(), nullable=False),
        sa.Column("ft_home", sa.SmallInteger(), nullable=False),
        sa.Column("ft_away", sa.SmallInteger(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("ht_home <= ft_home AND ht_away <= ft_away AND ht_home >= 0 AND ht_away >= 0",
                           name="ck_cup_results_scores"),
    )
    op.create_index("ix_cup_results_competition_kickoff", "cup_results", ["competition", "kickoff_time"])


def downgrade() -> None:
    op.drop_index("ix_cup_results_competition_kickoff", table_name="cup_results")
    op.drop_table("cup_results")
