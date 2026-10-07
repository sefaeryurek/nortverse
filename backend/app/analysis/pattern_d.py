"""Katman D — Cosine Similarity Pattern Matching (ARŞİV-3).

Bülten maçının FT ham oran vektörünü (35 boyut) DB'deki tüm geçmiş maçlarla
cosine similarity ile karşılaştırır ve en benzer Top-N maçı bulur.

Avantajları:
    - Pattern B gibi çok eşleşmez (sabit N sonuç)
    - Pattern C'nin 0-eşleşme sorunu yok (her zaman N kadar sonuç döner)
    - Benzerlik skoru ağırlık olarak kullanılabilir (ileride)

Performans:
    - 9,300+ vektör × 35 boyut = <15ms pure Python (numpy gerekmez)
    - Candidate cache ile sonraki çağrılar <1ms
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from sqlalchemy import func, select

from app.analysis.pattern_stats import PatternResult, compute_stats
from app.analysis.scores import ALL_SCORES, score_key
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)

_candidate_cache: list[tuple] | None = None
_candidate_cache_at: float = 0.0
_CACHE_TTL = 3600.0


def _to_vector(ratios: dict[str, float]) -> list[float]:
    return [ratios.get(score_key(h, a), 0.0) for h, a in ALL_SCORES]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _load_candidates(
    exclude_match_id: str | None = None,
    as_of: datetime | None = None,
) -> list[tuple]:
    global _candidate_cache, _candidate_cache_at

    now = time.monotonic()
    if _candidate_cache is not None and (now - _candidate_cache_at) < _CACHE_TTL:
        rows = _candidate_cache
    else:
        async with get_session() as session:
            filters = [
                Match.ft_all_ratios.isnot(None),
                Match.actual_ft_home.isnot(None),
                Match.actual_ft_away.isnot(None),
                Match.deleted_at.is_(None),
                Match.analyzed_at.is_not(None),
            ]
            if as_of is not None:
                known_at = func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at)
                filters.extend([
                    Match.kickoff_time < as_of,
                    known_at > Match.kickoff_time,
                    known_at <= as_of,
                    Match.analyzed_at < Match.kickoff_time,
                ])
            stmt = select(
                Match.match_id,
                Match.ft_all_ratios,
                Match.actual_ft_home, Match.actual_ft_away,
                Match.actual_ht_home, Match.actual_ht_away,
                Match.actual_h2_home, Match.actual_h2_away,
            ).where(*filters)
            rows = list((await session.execute(stmt)).all())
        _candidate_cache = rows
        _candidate_cache_at = now
        log.info("Pattern D candidate cache yüklendi: %d maç", len(rows))

    if exclude_match_id:
        rows = [r for r in rows if r[0] != exclude_match_id]
    return rows


async def find_pattern_d_all_periods(
    ft_ratios: dict[str, float],
    top_n: int = 20,
    min_similarity: float = 0.85,
    exclude_match_id: str | None = None,
    as_of: datetime | None = None,
) -> tuple[PatternResult | None, PatternResult | None, PatternResult | None]:
    """FT oran vektöründe cosine similarity ile en benzer Top-N maçı bulur.

    Args:
        ft_ratios: 35 skorun oranları (score_key -> float)
        top_n: Kaç aday seçilecek
        min_similarity: Minimum cosine similarity eşiği
        exclude_match_id: Analiz edilen maçın kendisi (self-exclusion)
        as_of: Temporal filtre

    Returns:
        (ht_result, h2_result, ft_result) — yeterli benzer maç yoksa None
    """
    if not ft_ratios:
        return None, None, None
    if as_of is not None and (as_of.tzinfo is None or as_of.utcoffset() is None):
        raise ValueError("as_of must be timezone-aware")

    target_vec = _to_vector(ft_ratios)
    if all(v == 0.0 for v in target_vec):
        return None, None, None

    candidates = await _load_candidates(exclude_match_id, as_of)
    if not candidates:
        return None, None, None

    scored: list[tuple[float, tuple]] = []
    for row in candidates:
        cand_ratios = row[1]
        if not isinstance(cand_ratios, dict):
            continue
        cand_vec = _to_vector(cand_ratios)
        sim = cosine_similarity(target_vec, cand_vec)
        if sim >= min_similarity:
            scored.append((sim, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_n]

    if not top:
        log.info("Pattern D: min_similarity=%.2f üzerinde eşleşme yok", min_similarity)
        return None, None, None

    class _Row:
        __slots__ = (
            "actual_ft_home", "actual_ft_away",
            "actual_ht_home", "actual_ht_away",
            "actual_h2_home", "actual_h2_away",
        )
        def __init__(self, r: tuple):
            self.actual_ft_home = r[2]
            self.actual_ft_away = r[3]
            self.actual_ht_home = r[4]
            self.actual_ht_away = r[5]
            self.actual_h2_home = r[6]
            self.actual_h2_away = r[7]

    matched_rows = [_Row(r) for _, r in top]

    log.info(
        "Pattern D: %d eşleşme (top sim=%.3f, min sim=%.3f)",
        len(matched_rows),
        top[0][0] if top else 0,
        top[-1][0] if top else 0,
    )

    results = [compute_stats(matched_rows, period) for period in ("ht", "h2", "ft")]
    return tuple(results)


async def find_matched_ids(
    ft_ratios: dict[str, float],
    top_n: int = 20,
    min_similarity: float = 0.85,
    exclude_match_id: str | None = None,
) -> list[tuple[str, float]]:
    """En benzer maçların (match_id, similarity) listesini döndürür."""
    if not ft_ratios:
        return []

    target_vec = _to_vector(ft_ratios)
    if all(v == 0.0 for v in target_vec):
        return []

    candidates = await _load_candidates(exclude_match_id)
    scored: list[tuple[float, str]] = []
    for row in candidates:
        cand_ratios = row[1]
        if not isinstance(cand_ratios, dict):
            continue
        sim = cosine_similarity(target_vec, _to_vector(cand_ratios))
        if sim >= min_similarity:
            scored.append((sim, row[0]))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [(mid, sim) for sim, mid in scored[:top_n]]


def invalidate_cache() -> None:
    global _candidate_cache, _candidate_cache_at
    _candidate_cache = None
    _candidate_cache_at = 0.0
