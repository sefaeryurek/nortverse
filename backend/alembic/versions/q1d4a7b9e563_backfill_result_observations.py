"""Seed immutable result observations for future v3 forecasts.

Revision ID: q1d4a7b9e563
Revises: p9c3f6a8d452

The ingestion trigger replaces ``ingested_at`` with deployment time. Historical
scores therefore become available only to forecasts created after this
migration; they are never backdated into an earlier as-of window.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "q1d4a7b9e563"
down_revision: Union[str, None] = "p9c3f6a8d452"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO match_final_result_observations (
            match_id, kickoff_time, ft_home, ft_away, observed_at,
            source, source_revision
        )
        SELECT
            match_id, kickoff_time, actual_ft_home, actual_ft_away,
            COALESCE(result_first_fetched_at, result_fetched_at),
            'legacy-match-v1',
            md5(concat_ws('|', match_id, actual_ft_home, actual_ft_away,
                          COALESCE(result_first_fetched_at, result_fetched_at)::text))
        FROM matches
        WHERE kickoff_time IS NOT NULL
          AND actual_ft_home IS NOT NULL AND actual_ft_away IS NOT NULL
          AND COALESCE(result_first_fetched_at, result_fetched_at) > kickoff_time
        ON CONFLICT (match_id, source, source_revision) DO NOTHING
    """)


def downgrade() -> None:
    raise RuntimeError(
        "q1d4a7b9e563 stores append-only audit observations and is intentionally irreversible"
    )
