"""Katman C — Tam Oran Pattern Matching (ARŞIV-2).

Bülten maçının ham oranlarını DB'deki geçmiş maçlarla ±0.5 aralığında karşılaştırır.
Tüm 35 skorda tolerans içinde kalan geçmiş maçların gerçek sonuçlarından istatistik çıkarır.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.analysis.pattern_stats import PatternResult, compute_stats
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)


def _ratios_match(
    target: dict[str, float],
    candidate: dict[str, float],
    tolerance: float,
) -> bool:
    """İki oran setinin tüm skorlarda ±tolerance içinde olup olmadığını kontrol eder."""
    for key, target_val in target.items():
        cand_val = candidate.get(key)
        if cand_val is None:
            return False
        if abs(target_val - cand_val) > tolerance:
            return False
    return True


async def find_pattern_c_matches(
    period: str,
    all_ratios: dict[str, float],
    min_matches: int = 5,
    tolerance: float = 0.5,
) -> PatternResult | None:
    """Belirtilen periyot oranlarıyla ±tolerance eşleşen geçmiş maçları bul.

    Args:
        period: "ht", "h2" veya "ft"
        all_ratios: Bülten maçının 35 oranı {"1-0": 5.5, ...}
        min_matches: Minimum eşleşme sayısı
        tolerance: Her skor için izin verilen oran farkı (±0.5)

    Returns:
        PatternResult veya None (eşleşme < min_matches ise)
    """
    if period == "ht":
        ratios_col = Match.ht_all_ratios
        actual_check = Match.actual_ht_home.isnot(None)
        ratios_attr = "ht_all_ratios"
    elif period == "h2":
        ratios_col = Match.h2_all_ratios
        actual_check = Match.actual_h2_home.isnot(None)
        ratios_attr = "h2_all_ratios"
    else:
        ratios_col = Match.ft_all_ratios
        actual_check = Match.actual_ft_home.isnot(None)
        ratios_attr = "ft_all_ratios"

    async with get_session() as session:
        stmt = (
            select(Match)
            .where(
                ratios_col.isnot(None),
                actual_check,
            )
        )
        rows = (await session.execute(stmt)).scalars().all()

    matched = [
        row for row in rows
        if getattr(row, ratios_attr)
        and _ratios_match(all_ratios, getattr(row, ratios_attr), tolerance)
    ]

    if len(matched) < min_matches:
        log.info(
            "Katman C [%s]: %d eşleşme (minimum %d, tolerans ±%.1f) — atlandı",
            period,
            len(matched),
            min_matches,
            tolerance,
        )
        return None

    log.info("Katman C [%s]: %d eşleşme bulundu", period, len(matched))
    return compute_stats(matched, period)
