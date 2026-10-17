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

from sqlalchemy import Float, cast, select
from sqlalchemy.dialects.postgresql import JSONB

from app.analysis.pattern_b import _temporal_weights, candidate_filters
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
    league_name: str | None = None,
    match_cap: int | None = None,
    temporal_half_life: float = 0.0,
) -> tuple[PatternResult | None, PatternResult | None, PatternResult | None]:
    """FT oranlarıyla eşleşen geçmiş maçlar için IY, 2Y ve FT istatistiklerini döndür.

    Tüm periyotlar aynı eşleşme setini kullanır.

    Args:
        exclude_match_id: Bu match_id'yi sonuçlardan çıkar (analiz edilen maçın kendisi)
        league_name: Lig filtresi — sadece aynı lig (başka lige düşülmez)
        match_cap: Maksimum eşleşme sayısı (en yakın N maç, sinyal seyrelmesini önler)

    Returns:
        (ht_result, h2_result, ft_result) — eşleşme yetersizse hepsi None
    """
    if type(min_matches) is not int or min_matches < 1:
        raise ValueError("min_matches must be a positive integer")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")
    if as_of is None or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if not ft_ratios:
        return None, None, None
    if not _ratios_match(ft_ratios, ft_ratios, 0):
        raise ValueError("ratios must contain finite non-negative numbers")

    filters = [
        Match.ft_all_ratios.isnot(None),
        Match.actual_ft_home.isnot(None),
        Match.actual_ft_away.isnot(None),
        *candidate_filters(as_of),
    ]
    if league_name:
        filters.append(Match.league_name == league_name)
    if exclude_match_id:
        filters.append(Match.match_id != exclude_match_id)
    if tolerance == 0.0:
        filters.append(cast(Match.ft_all_ratios, JSONB) == cast(ft_ratios, JSONB))
    else:
        for key, target_val in ft_ratios.items():
            ratio_expr = cast(Match.ft_all_ratios[key].as_string(), Float)
            filters.append(ratio_expr.between(target_val - tolerance, target_val + tolerance))
    stmt = select(
        Match.match_id,
        Match.actual_ft_home, Match.actual_ft_away,
        Match.actual_ht_home, Match.actual_ht_away,
        Match.actual_h2_home, Match.actual_h2_away,
        Match.kickoff_time,
    ).where(*filters).order_by(Match.kickoff_time.desc())
    if match_cap and match_cap > 0:
        stmt = stmt.limit(match_cap)
    async with get_session() as session:
        matched = list((await session.execute(stmt)).all())

    if len(matched) < min_matches:
        log.debug("Katman C: %d eşleşme (minimum %d, tolerans ±%.2f) — atlandı",
                  len(matched), min_matches, tolerance)
        return None, None, None

    log.debug("Katman C: %d eşleşme bulundu (tolerance=%.2f)", len(matched), tolerance)
    weights = _temporal_weights(matched, as_of, temporal_half_life) if temporal_half_life > 0 else None
    results = [compute_stats(matched, period, weights=weights) for period in ("ht", "h2", "ft")]
    return tuple(result if result is not None and result.match_count >= min_matches else None
                 for result in results)


async def find_pattern_c_adaptive(
    ft_ratios: dict[str, float],
    min_matches: int = 3,
    base_tolerance: float = 0.5,
    max_tolerance: float = 1.0,
    tolerance_step: float = 0.25,
    exclude_match_id: str | None = None,
    as_of: datetime | None = None,
    league_name: str | None = None,
    match_cap: int | None = None,
    temporal_half_life: float = 0.0,
) -> tuple[PatternResult | None, PatternResult | None, PatternResult | None]:
    """Adım adım tolerance artırarak yeterli eşleşme bulmaya çalışır.

    base_tolerance ile başlar; eşleşme sayısı min_matches'ın altındaysa
    tolerance_step kadar artırıp tekrar dener. max_tolerance'a ulaşınca durur.
    """
    tol = base_tolerance
    last_result = (None, None, None)
    while tol <= max_tolerance + 1e-9:
        result = await find_pattern_c_all_periods(
            ft_ratios,
            min_matches=1,
            tolerance=round(tol, 4),
            exclude_match_id=exclude_match_id,
            as_of=as_of,
            league_name=league_name,
            match_cap=match_cap,
            temporal_half_life=temporal_half_life,
        )
        last_result = result
        ft_result = result[2]
        if ft_result is not None and ft_result.match_count >= min_matches:
            return result
        tol += tolerance_step

    log.debug("Katman C adaptive: max_tolerance=%.2f'ye kadar min %d eşleşme yok", max_tolerance, min_matches)
    return last_result
