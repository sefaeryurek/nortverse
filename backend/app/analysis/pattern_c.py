"""Katman C — Tam Oran Pattern Matching (ARŞIV-2).

Bülten maçının FT ham oranlarını DB'deki geçmiş maçlarla karşılaştırır.
Eşleşen maçlar için IY, 2Y ve FT istatistiklerini aynı setten hesaplar.

Neden tek set?
    105 oran (35 skor × 3 periyot) aynı h2h/form verisinden türetilir.
    FT oranlarıyla benzer bulunan maçlar IY/2Y için de benzerdir.
    Tek eşleşme setiyle IY/2Y/FT tutarlı sonuç verir; seti parçalamak
    bir periyotta "var" diğerinde "yok" anomalisine yol açar.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime

from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import JSONB

from app.analysis.pattern_stats import PatternResult, compute_stats
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)


def _ratios_match(
    target: dict[str, float],
    candidate: dict[str, float],
    tolerance: float,
) -> bool:
    """İki oran setinin tüm skorlarda ±tolerance içinde olup olmadığını kontrol eder.

    Sadece tolerance > 0 yolunda kullanılır (Sprint 8.10 öncesi davranış).
    Tolerance == 0 için DB-side JSONB equality kullanılır (egress optimize).
    """
    if not target or target.keys() != candidate.keys():
        return False
    if not math.isfinite(tolerance) or tolerance < 0:
        return False
    for key, target_val in target.items():
        cand_val = candidate.get(key)
        if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
               for value in (target_val, cand_val)):
            return False
        if abs(target_val - cand_val) > tolerance:
            return False
    return True


async def find_pattern_c_all_periods(
    ft_ratios: dict[str, float],
    min_matches: int = 1,
    tolerance: float = 0.0,
    exclude_match_id: str | None = None,
    as_of: datetime | None = None,
) -> tuple[PatternResult | None, PatternResult | None, PatternResult | None]:
    """FT oranlarıyla eşleşen geçmiş maçlar için IY, 2Y ve FT istatistiklerini döndür.

    Tüm periyotlar aynı eşleşme setini kullanır.

    Sprint 8.9 değişiklikleri:
    - tolerance 0.5 → 0.0 (tam eşleşme; oranlar 0.5 katı olduğundan birebir aynı)
    - min_matches 5 → 1 (sıkı tolerance ile az eşleşme normal; UI 1-4 maçı "düşük güven" rozetiyle gösterir)

    Sprint 8.10 — Egress optimizasyonu:
    - tolerance == 0.0: DB-side JSONB equality WHERE filter (~50KB egress / çağrı)
      Eski yol: tüm 13K+ satır çekilir Python'da filter (~130MB egress / çağrı)
      Etki: %99.96 azalma — Supabase Fair Use kotasını korur
    - tolerance > 0.0: eski yol (fuzzy match, fallback)

    Args:
        exclude_match_id: Bu match_id'yi sonuçlardan çıkar (analiz edilen maçın kendisi)

    Returns:
        (ht_result, h2_result, ft_result) — eşleşme yetersizse hepsi None
    """
    if type(min_matches) is not int or min_matches < 1:
        raise ValueError("min_matches must be a positive integer")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")
    if not ft_ratios:
        return None, None, None
    if not _ratios_match(ft_ratios, ft_ratios, 0):
        raise ValueError("ratios must contain finite non-negative numbers")
    if tolerance == 0.0:
        # HIZLI YOL — DB-side JSONB equality (Sprint 8.10)
        # PostgreSQL JSONB karşılaştırması kanoniktir (key sırası önemsiz; aynı içerik = aynı).
        async with get_session() as session:
            filters = [
                cast(Match.ft_all_ratios, JSONB) == cast(ft_ratios, JSONB),
                Match.actual_ft_home.isnot(None),
                Match.actual_ft_away.isnot(None),
                Match.deleted_at.is_(None),  # Sprint 8.9: soft-deleted (kupa) hariç
            ]
            if exclude_match_id:
                filters.append(Match.match_id != exclude_match_id)
            if as_of is not None:
                known_at = func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at)
                filters.extend([
                    Match.kickoff_time < as_of,
                    known_at > Match.kickoff_time,
                    known_at <= as_of,
                    Match.analyzed_at.is_not(None),
                    Match.analyzed_at < Match.kickoff_time,
                ])
            stmt = select(
                Match.actual_ft_home, Match.actual_ft_away,
                Match.actual_ht_home, Match.actual_ht_away,
                Match.actual_h2_home, Match.actual_h2_away,
            ).where(*filters)
            matched = list((await session.execute(stmt)).all())
    else:
        # YAVAŞ YOL — fuzzy match (tolerance > 0), tüm satırlar çekilir
        async with get_session() as session:
            filters = [
                Match.ft_all_ratios.isnot(None),
                Match.actual_ft_home.isnot(None),
                Match.actual_ft_away.isnot(None),
                Match.deleted_at.is_(None),
            ]
            if exclude_match_id:
                filters.append(Match.match_id != exclude_match_id)
            if as_of is not None:
                known_at = func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at)
                filters.extend([
                    Match.kickoff_time < as_of,
                    known_at > Match.kickoff_time,
                    known_at <= as_of,
                    Match.analyzed_at.is_not(None),
                    Match.analyzed_at < Match.kickoff_time,
                ])
            stmt = select(
                Match.ft_all_ratios,
                Match.actual_ft_home, Match.actual_ft_away,
                Match.actual_ht_home, Match.actual_ht_away,
                Match.actual_h2_home, Match.actual_h2_away,
            ).where(*filters)
            rows = (await session.execute(stmt)).all()
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

    log.info("Katman C: %d eşleşme bulundu (tolerance=%.1f)", len(matched), tolerance)
    results = [compute_stats(matched, period) for period in ("ht", "h2", "ft")]
    return tuple(result if result is not None and result.match_count >= min_matches else None
                 for result in results)
