"""Record successful pattern computations, including those with no matches.

Revision ID: h8c91e7a2b04
Revises: g4d2a7c9b815
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "h8c91e7a2b04"
down_revision: Union[str, None] = "g4d2a7c9b815"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("pattern_computed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "pattern_computed_at")
