"""Katman C — Tam Oran Pattern Matching (ARŞIV-2).

Bülten maçının FT ham oranlarını DB'deki geçmiş maçlarla ±0.5 aralığında karşılaştırır.
Eşleşen maçlar için IY, 2Y ve FT istatistiklerini aynı setten hesaplar.

Neden tek set?
    105 oran (35 skor × 3 periyot) aynı h2h/form verisinden türetilir.
    FT oranlarıyla benzer bulunan maçlar IY/2Y için de benzerdir.
    Tek eşleşme setiyle IY/2Y/FT tutarlı sonuç verir; seti parçalamak
    bir periyotta "var" diğerinde "yok" anomalisine yol açar.
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


async def find_pattern_c_all_periods(
    ft_ratios: dict[str, float],
    min_matches: int = 5,
    tolerance: float = 0.5,
) -> tuple[PatternResult | None, PatternResult | None, PatternResult | None]:
    """FT oranlarıyla eşleşen geçmiş maçlar için IY, 2Y ve FT istatistiklerini döndür.

    Tüm periyotlar aynı eşleşme setini kullanır.

    Returns:
        (ht_result, h2_result, ft_result) — eşleşme yetersizse hepsi None
    """
    async with get_session() as session:
        stmt = select(Match).where(
            Match.ft_all_ratios.isnot(None),
            Match.actual_ft_home.isnot(None),
        )
        rows = (await session.execute(stmt)).scalars().all()

    matched = [
        row for row in rows
        if row.ft_all_ratios and _ratios_match(ft_ratios, row.ft_all_ratios, tolerance)
    ]

    if len(matched) < min_matches:
        log.info(
            "Katman C: %d eşleşme (minimum %d, tolerans ±%.1f) — atlandı",
            len(matched),
            min_matches,
            tolerance,
        )
        return None, None, None

    log.info("Katman C: %d eşleşme bulundu", len(matched))
    return (
        compute_stats(matched, "ht"),
        compute_stats(matched, "h2"),
        compute_stats(matched, "ft"),
    )
