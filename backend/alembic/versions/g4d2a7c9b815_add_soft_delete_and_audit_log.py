"""add_soft_delete_and_audit_log

Sprint 8.9 — Veri Bütünlüğü.
- matches tablosuna `deleted_at` ve `deleted_reason` kolonları eklenir (soft delete)
- audit_log tablosu oluşturulur — tüm prune/silme/restore işlemleri kayda alınır

Revision ID: g4d2a7c9b815
Revises: f5c8d2a1b394
Create Date: 2026-05-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'g4d2a7c9b815'
down_revision: Union[str, None] = 'f5c8d2a1b394'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Soft delete kolonları
    op.add_column("matches", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("matches", sa.Column("deleted_reason", sa.String(length=50), nullable=True))
    op.create_index(
        "ix_matches_deleted_at",
        "matches",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),  # active rows için partial index
    )

    # audit_log tablosu
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("target_match_id", sa.String(length=20), nullable=True),
        sa.Column("actor", sa.String(length=100), nullable=True),
        sa.Column("details", JSONB, nullable=True),
    )
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_target", "audit_log", ["target_match_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_target", table_name="audit_log")
    op.drop_index("ix_audit_log_timestamp", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_matches_deleted_at", table_name="matches")
    op.drop_column("matches", "deleted_reason")
    op.drop_column("matches", "deleted_at")
