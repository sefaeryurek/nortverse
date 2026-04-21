"""Katman C — Tam Oran Pattern Matching (ARŞIV-2).

Bülten maçının FT ham oranlarını DB'deki geçmiş maçlarla ±0.5 aralığında karşılaştırır.
Tüm 35 skorda tolerans içinde kalan geçmiş maçların gerçek sonuçlarından istatistik çıkarır.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select

from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)


@dataclass
class PatternCResult:
    """Katman C istatistik sonucu."""

    match_count: int
    kg_var_pct: float    # Her iki takım da gol attı (%)
    over_25_pct: float   # Toplam gol ≥ 3 (%)
    result_1_pct: float  # Ev galibiyeti (%)
    result_x_pct: float  # Beraberlik (%)
    result_2_pct: float  # Deplasman galibiyeti (%)


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
    ft_all_ratios: dict[str, float],
    min_matches: int = 5,
    tolerance: float = 0.5,
) -> PatternCResult | None:
    """FT oranlarıyla ±tolerance eşleşen geçmiş maçları bul ve istatistik üret.

    DB'den gerçek sonucu olan tüm maçları çeker, Python tarafında fuzzy matching yapar.
    35 skorun tamamında tolerans sağlanması gerekir (katı eşleşme).

    Args:
        ft_all_ratios: Bülten maçının 35 FT oranı {"1-0": 5.5, "0-1": 4.0, ...}
        min_matches: Minimum eşleşme sayısı (default 5)
        tolerance: Her skor için izin verilen oran farkı (default ±0.5)

    Returns:
        PatternCResult veya None (eşleşme < min_matches ise)
    """
    async with get_session() as session:
        stmt = (
            select(Match)
            .where(
                Match.ft_all_ratios.isnot(None),
                Match.actual_ft_home.isnot(None),
                Match.actual_ft_away.isnot(None),
            )
        )
        rows = (await session.execute(stmt)).scalars().all()

    matched = [
        row for row in rows
        if row.ft_all_ratios and _ratios_match(ft_all_ratios, row.ft_all_ratios, tolerance)
    ]

    if len(matched) < min_matches:
        log.info(
            "Katman C: %d eşleşme (minimum %d gerekli, tolerans ±%.1f) — atlandı",
            len(matched),
            min_matches,
            tolerance,
        )
        return None

    total = len(matched)
    kg_var = 0
    over_25 = 0
    win_1 = 0
    draw_x = 0
    win_2 = 0

    for row in matched:
        h = row.actual_ft_home
        a = row.actual_ft_away
        if h > 0 and a > 0:
            kg_var += 1
        if h + a >= 3:
            over_25 += 1
        if h > a:
            win_1 += 1
        elif h == a:
            draw_x += 1
        else:
            win_2 += 1

    log.info(
        "Katman C: %d eşleşme — 1:%.0f%% X:%.0f%% 2:%.0f%%",
        total,
        win_1 / total * 100,
        draw_x / total * 100,
        win_2 / total * 100,
    )

    return PatternCResult(
        match_count=total,
        kg_var_pct=round(kg_var / total * 100, 1),
        over_25_pct=round(over_25 / total * 100, 1),
        result_1_pct=round(win_1 / total * 100, 1),
        result_x_pct=round(draw_x / total * 100, 1),
        result_2_pct=round(win_2 / total * 100, 1),
    )
