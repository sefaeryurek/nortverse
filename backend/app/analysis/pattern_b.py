"""Katman B — Pattern Matching (ARŞIV-1).

Bülten maçının MS1+MSX+MS2 skor setini DB'deki geçmiş maçlarla karşılaştırır.
Tam aynı skor setine sahip maçların gerçek sonuçlarından istatistik çıkarır.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB

from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)


@dataclass
class PatternBResult:
    """Katman B istatistik sonucu."""

    match_count: int
    kg_var_pct: float    # Her iki takım da gol attı (%)
    over_25_pct: float   # Toplam gol ≥ 3 (%)
    result_1_pct: float  # Ev galibiyeti (%)
    result_x_pct: float  # Beraberlik (%)
    result_2_pct: float  # Deplasman galibiyeti (%)


async def find_pattern_b_matches(
    ft_scores_1: list[str],
    ft_scores_x: list[str],
    ft_scores_2: list[str],
    min_matches: int = 5,
) -> PatternBResult | None:
    """Aynı MS skor setine sahip geçmiş maçları bul ve istatistik üret.

    JSONB equality: JSONB sütununu Python listesiyle doğrudan karşılaştırır.
    Sadece gerçek sonucu olan (actual_ft_home IS NOT NULL) maçlar kullanılır.

    Returns:
        PatternBResult veya None (eşleşme < min_matches ise)
    """
    async with get_session() as session:
        stmt = (
            select(Match)
            .where(
                Match.ft_scores_1.cast(JSONB) == cast(ft_scores_1, JSONB),
                Match.ft_scores_x.cast(JSONB) == cast(ft_scores_x, JSONB),
                Match.ft_scores_2.cast(JSONB) == cast(ft_scores_2, JSONB),
                Match.actual_ft_home.isnot(None),
                Match.actual_ft_away.isnot(None),
            )
        )
        rows = (await session.execute(stmt)).scalars().all()

    if len(rows) < min_matches:
        log.info(
            "Katman B: %d eşleşme (minimum %d gerekli) — atlandı",
            len(rows),
            min_matches,
        )
        return None

    total = len(rows)
    kg_var = 0
    over_25 = 0
    win_1 = 0
    draw_x = 0
    win_2 = 0

    for row in rows:
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
        "Katman B: %d eşleşme — 1:%.0f%% X:%.0f%% 2:%.0f%%",
        total,
        win_1 / total * 100,
        draw_x / total * 100,
        win_2 / total * 100,
    )

    return PatternBResult(
        match_count=total,
        kg_var_pct=round(kg_var / total * 100, 1),
        over_25_pct=round(over_25 / total * 100, 1),
        result_1_pct=round(win_1 / total * 100, 1),
        result_x_pct=round(draw_x / total * 100, 1),
        result_2_pct=round(win_2 / total * 100, 1),
    )
