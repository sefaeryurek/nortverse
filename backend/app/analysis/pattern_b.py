"""Katman B — Pattern Matching (ARŞIV-1).

Bülten maçının skor setini (MS1/MSX/MS2) DB'deki geçmiş maçlarla karşılaştırır.
Tam aynı skor setine sahip maçların gerçek sonuçlarından istatistik çıkarır.
"""

from __future__ import annotations

import logging

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB

from app.analysis.pattern_stats import PatternResult, compute_stats
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)


async def find_pattern_b_matches(
    period: str,
    scores_1: list[str],
    scores_x: list[str],
    scores_2: list[str],
    min_matches: int = 5,
    exclude_match_id: str | None = None,
) -> PatternResult | None:
    """Aynı periyot skor setine sahip geçmiş maçları bul ve istatistik üret.

    Args:
        period: "ht", "h2" veya "ft"
        scores_1, scores_x, scores_2: Eşleştirilecek skor listeleri
        min_matches: Minimum eşleşme sayısı
        exclude_match_id: Bu match_id'yi sonuçlardan çıkar (analiz edilen maçın kendisi)

    Returns:
        PatternResult veya None (eşleşme < min_matches ise)
    """
    if period == "ht":
        col_1, col_x, col_2 = Match.ht_scores_1, Match.ht_scores_x, Match.ht_scores_2
        actual_check = Match.actual_ht_home.isnot(None)
    elif period == "h2":
        col_1, col_x, col_2 = Match.h2_scores_1, Match.h2_scores_x, Match.h2_scores_2
        actual_check = Match.actual_h2_home.isnot(None)
    else:
        col_1, col_x, col_2 = Match.ft_scores_1, Match.ft_scores_x, Match.ft_scores_2
        actual_check = Match.actual_ft_home.isnot(None)

    async with get_session() as session:
        filters = [
            col_1.cast(JSONB) == cast(scores_1, JSONB),
            col_x.cast(JSONB) == cast(scores_x, JSONB),
            col_2.cast(JSONB) == cast(scores_2, JSONB),
            actual_check,
            Match.deleted_at.is_(None),  # Sprint 8.9: soft-deleted (kupa) maçlar arşivde sayılmaz
        ]
        if exclude_match_id:
            filters.append(Match.match_id != exclude_match_id)
        stmt = select(Match).where(*filters)
        rows = (await session.execute(stmt)).scalars().all()

    if len(rows) < min_matches:
        log.info(
            "Katman B [%s]: %d eşleşme (minimum %d) — atlandı",
            period,
            len(rows),
            min_matches,
        )
        return None

    log.info("Katman B [%s]: %d eşleşme bulundu", period, len(rows))
    return compute_stats(list(rows), period)
