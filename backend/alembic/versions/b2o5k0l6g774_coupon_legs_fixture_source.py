"""Kupondaş bülten tabanlı bacak (Sprint 94 J6, K4): coupon_legs → matches bağı kalkar, `source` kolonu

Analiz edilmemiş bülten maçları (kupa dahil) da kupona eklenebilsin diye bacak artık `matches` satırı istemez;
maç bilgisi ve sonucu önce `matches`'tan, yoksa `fixture_cache`'ten okunur. `source` kayıt anında maçın nereden
geldiğini söyler ('db' | 'fixture'). Kolon varsayılanla eklendiği için satır tetikleyicisi çalışmaz (değişmezlik
korunur).

Revision ID: b2o5k0l6g774
Revises: a1n4j9k5f663
Create Date: 2026-10-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2o5k0l6g774"
down_revision: Union[str, None] = "a1n4j9k5f663"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("coupon_legs_match_id_fkey", "coupon_legs", type_="foreignkey")
    op.add_column("coupon_legs", sa.Column("source", sa.String(10), nullable=False, server_default="db"))
    op.create_check_constraint("ck_coupon_legs_source", "coupon_legs", "source IN ('db', 'fixture')")


def downgrade() -> None:
    # Bülten tabanlı bacak varsa bağ geri kurulamaz → NOT VALID (eski satırlar denetlenmez, yeniler denetlenir)
    op.drop_constraint("ck_coupon_legs_source", "coupon_legs", type_="check")
    op.drop_column("coupon_legs", "source")
    op.execute("ALTER TABLE coupon_legs ADD CONSTRAINT coupon_legs_match_id_fkey "
               "FOREIGN KEY (match_id) REFERENCES matches (match_id) NOT VALID")
