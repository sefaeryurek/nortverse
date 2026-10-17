"""Katman D — Cosine Similarity Pattern Matching (ARŞİV-3).

Bülten maçının FT ham oran vektörünü (35 boyut) aynı ligdeki geçmiş maçlarla
cosine similarity ile karşılaştırır; min_similarity üzerindeki TÜM maçları alır
(adet sınırı yok).

IDF ağırlıklı: nadir skor oranlarındaki benzerlik daha fazla ayırt edici
bilgi taşıdığından, her boyut IDF (Inverse Document Frequency) ile ağırlıklandırılır.

Performans: aday havuzu bir kez yüklenir (1 saat TTL), vektörler IDF ile
ağırlıklandırılıp normalize edilerek saklanır; her çağrı sadece nokta çarpımı yapar.
Zaman (as_of) ve lig filtresi bellekte uygulanır → cache her maçta yeniden yüklenmez.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.analysis.pattern_b import RESULT_KNOWN_DELAY
from app.analysis.pattern_stats import PatternResult, compute_stats
from app.analysis.scores import ALL_SCORES, score_key
from app.config import ANALYSIS
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)

_CACHE_TTL = 3600.0
# IDF ağırlıkları sadece bu tarihten önce oynanmış maçlardan: 2023-07 sonrası backtest'te gelecek bilgisi yok.
IDF_CUTOFF = datetime(2023, 7, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class _Candidate:
    match_id: str
    unit_vec: tuple[float, ...]
    league_name: str | None
    kickoff_time: datetime
    actual_ft_home: int | None
    actual_ft_away: int | None
    actual_ht_home: int | None
    actual_ht_away: int | None
    actual_h2_home: int | None
    actual_h2_away: int | None


@dataclass(frozen=True)
class _Pool:
    candidates: list[_Candidate]
    by_league: dict[str | None, list[_Candidate]]
    idf: list[float]
    loaded_at: float


_pool: _Pool | None = None
_pool_lock = asyncio.Lock()


def _to_vector(ratios: dict[str, float]) -> list[float]:
    return [ratios.get(score_key(h, a), 0.0) for h, a in ALL_SCORES]


def _compute_idf_weights(candidates: list[tuple]) -> list[float]:
    """Her skor boyutu için IDF ağırlığı hesaplar.

    IDF = log(1 + N / (1 + df_i)) burada df_i = o boyutta sıfırdan farklı değere
    sahip maç sayısı. Nadir skorlar yüksek ağırlık alır.
    """
    n = len(candidates)
    if n == 0:
        return [1.0] * len(ALL_SCORES)

    df = [0] * len(ALL_SCORES)
    for row in candidates:
        ratios = row[1]
        if not isinstance(ratios, dict):
            continue
        for i, (h, a) in enumerate(ALL_SCORES):
            if ratios.get(score_key(h, a), 0.0) > 0.0:
                df[i] += 1

    weights = [math.log(1.0 + n / (1.0 + d)) for d in df]
    max_w = max(weights) if weights else 1.0
    if max_w > 0:
        weights = [w / max_w for w in weights]
    return weights


def cosine_similarity(a: list[float], b: list[float], weights: list[float] | None = None) -> float:
    if weights:
        a = [x * w for x, w in zip(a, weights)]
        b = [y * w for y, w in zip(b, weights)]
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _unit(vec: list[float], weights: list[float]) -> tuple[float, ...] | None:
    weighted = [x * w for x, w in zip(vec, weights)]
    norm = math.sqrt(sum(x * x for x in weighted))
    if norm == 0.0:
        return None
    return tuple(x / norm for x in weighted)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _build_pool(rows: list[tuple]) -> _Pool:
    idf_rows = [r for r in rows if r[9] is not None and _aware(r[9]) < IDF_CUTOFF]
    idf = _compute_idf_weights(idf_rows or rows)
    candidates: list[_Candidate] = []
    for r in rows:
        if not isinstance(r[1], dict) or r[9] is None:
            continue
        unit = _unit(_to_vector(r[1]), idf)
        if unit is None:
            continue
        kickoff = _aware(r[9])
        candidates.append(_Candidate(
            match_id=str(r[0]), unit_vec=unit, league_name=r[8], kickoff_time=kickoff,
            actual_ft_home=r[2], actual_ft_away=r[3],
            actual_ht_home=r[4], actual_ht_away=r[5],
            actual_h2_home=r[6], actual_h2_away=r[7],
        ))
    by_league: dict[str | None, list[_Candidate]] = {}
    for c in candidates:
        by_league.setdefault(c.league_name, []).append(c)
    return _Pool(candidates=candidates, by_league=by_league, idf=idf, loaded_at=time.monotonic())


async def _load_pool() -> _Pool:
    """Sonucu bilinen tüm aktif maçları bir kez yükler (as_of'tan bağımsız).

    Kilit: soğuk önbellekte eşzamanlı istekler havuzu bir kez kurar.
    Kurulum (vektör normalizasyonu) olay döngüsünü bloklamamak için thread'de yapılır.
    """
    global _pool
    if _pool is not None and time.monotonic() - _pool.loaded_at < _CACHE_TTL:
        return _pool
    async with _pool_lock:
        if _pool is not None and time.monotonic() - _pool.loaded_at < _CACHE_TTL:
            return _pool
        known_at = func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at)
        stmt = select(
            Match.match_id,
            Match.ft_all_ratios,
            Match.actual_ft_home, Match.actual_ft_away,
            Match.actual_ht_home, Match.actual_ht_away,
            Match.actual_h2_home, Match.actual_h2_away,
            Match.league_name,
            Match.kickoff_time,
        ).where(
            Match.ft_all_ratios.isnot(None),
            Match.actual_ft_home.isnot(None),
            Match.actual_ft_away.isnot(None),
            Match.deleted_at.is_(None),
            Match.kickoff_time.isnot(None),
            known_at > Match.kickoff_time,
        )
        async with get_session() as session:
            rows = list((await session.execute(stmt)).all())
        _pool = await asyncio.to_thread(_build_pool, rows)
        log.info("Pattern D aday havuzu yüklendi: %d maç", len(_pool.candidates))
        return _pool


class _MatchedRow:
    """compute_stats için satır — similarity, liste sırası için taşınır."""

    __slots__ = (
        "match_id", "similarity",
        "actual_ft_home", "actual_ft_away",
        "actual_ht_home", "actual_ht_away",
        "actual_h2_home", "actual_h2_away",
    )

    def __init__(self, c: _Candidate, similarity: float):
        self.match_id = c.match_id
        self.similarity = round(similarity, 4)
        self.actual_ft_home = c.actual_ft_home
        self.actual_ft_away = c.actual_ft_away
        self.actual_ht_home = c.actual_ht_home
        self.actual_ht_away = c.actual_ht_away
        self.actual_h2_home = c.actual_h2_home
        self.actual_h2_away = c.actual_h2_away


async def find_pattern_d_all_periods(
    ft_ratios: dict[str, float],
    min_similarity: float = 0.97,
    exclude_match_id: str | None = None,
    as_of: datetime | None = None,
    league_name: str | None = None,
    min_matches: int = 1,
) -> tuple[PatternResult | None, PatternResult | None, PatternResult | None]:
    """FT oran vektöründe benzerliği min_similarity üzerindeki tüm maçları bulur.

    Args:
        ft_ratios: 35 skorun oranları (score_key -> float)
        min_similarity: Minimum cosine similarity eşiği (adet sınırı yok)
        exclude_match_id: Analiz edilen maçın kendisi (self-exclusion)
        as_of: Sadece bu andan önce sonucu bilinen maçlar aday olur
        league_name: Sadece aynı lig (başka lige düşülmez); None ise tüm ligler
        min_matches: Bu sayının altında eşleşme varsa sonuç yok (küçük örneklem %100'leri)

    Returns:
        (ht_result, h2_result, ft_result) — benzer maç yoksa None
    """
    if not ft_ratios:
        return None, None, None
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")

    pool = await _load_pool()
    target = _unit(_to_vector(ft_ratios), pool.idf)
    if target is None:
        return None, None, None

    cutoff = as_of - RESULT_KNOWN_DELAY
    candidates = pool.by_league.get(league_name, []) if league_name else pool.candidates
    half_life = ANALYSIS.temporal_decay_half_life_years

    scored: list[tuple[float, float, _Candidate]] = []
    for c in candidates:
        if c.kickoff_time > cutoff or c.match_id == exclude_match_id:
            continue
        sim = sum(x * y for x, y in zip(target, c.unit_vec))
        if sim < min_similarity:
            continue
        age_years = (as_of - c.kickoff_time).total_seconds() / (365.25 * 86400)
        tw = 0.5 ** (max(0.0, age_years) / half_life) if half_life > 0 else 1.0
        scored.append((sim, sim * tw, c))

    if len(scored) < max(1, min_matches):
        log.debug("Pattern D: %d eşleşme (minimum %d)", len(scored), min_matches)
        return None, None, None

    scored.sort(key=lambda x: x[0], reverse=True)
    rows = [_MatchedRow(c, sim) for sim, _, c in scored]
    weights = [w for _, w, _ in scored]
    log.debug("Pattern D: %d eşleşme (en yüksek benzerlik=%.3f)", len(rows), scored[0][0])
    results = [compute_stats(rows, period, weights=weights) for period in ("ht", "h2", "ft")]
    return tuple(results)


def invalidate_cache() -> None:
    global _pool
    _pool = None
