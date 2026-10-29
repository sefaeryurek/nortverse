"""Katman D — Arşiv-3: takım gücü uzayında en yakın maçlar (Sprint 91 Faz 4, algoritma d4).

Eski A3 (35 boyutlu oran vektörü + kosinüs) çok gevşekti: oran(h,a) ≈ f(h) + g(a) yapısı yüzünden
rastgele iki maçın kosinüsü medyan 0,85 çıkıyordu, 0,97 eşiğinde bile ilgisiz yüzlerce maç eşleşiyordu
(maç öncesi MS %44,2). Yeni A3: maçın maç öncesi beklenen golleri (λ ev, λ dep — `live_poisson`
takım gücü modeli, başlama anından önceki veriyle) aynı ligdeki geçmiş maçlarınkine log uzayında en
yakın K maç (varsayılan 200). Ajan ölçümü: MS %50,7.

Benzerlik (ekranda) = exp(−uzaklık): 1'e yakın = aynı güç dengesi. İstatistiklerde yakın tarihli maçlar
daha ağırlıklı (temporal decay). Arşivler artık karar vermez, sadece bilgi (Sprint 91).
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.analysis.freshness import ResultsWatch, results_marker
from app.analysis.pattern_b import RESULT_KNOWN_DELAY
from app.analysis.pattern_stats import PatternResult, compute_stats
from app.config import ANALYSIS
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)

_CACHE_TTL = 3600.0


@dataclass(frozen=True)
class _Candidate:
    match_id: str
    log_h: float
    log_a: float
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
    by_league: dict[str | None, list[_Candidate]]
    loaded_at: float


_pool: _Pool | None = None
_pool_lock = asyncio.Lock()
# API süreci pipeline/skor güncellemesini (ayrı CLI süreci) bu işaretle fark eder.
_pool_watch = ResultsWatch()


async def _pool_fresh() -> bool:
    return (_pool is not None and time.monotonic() - _pool.loaded_at < _CACHE_TTL
            and not await _pool_watch.stale())


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _build_pool(rows: list[tuple]) -> _Pool:
    by_league: dict[str | None, list[_Candidate]] = {}
    for r in rows:
        lam_h, lam_a = r[1], r[2]
        if not lam_h or not lam_a or r[10] is None:
            continue
        by_league.setdefault(r[9], []).append(_Candidate(
            match_id=str(r[0]), log_h=math.log(lam_h), log_a=math.log(lam_a), league_name=r[9],
            kickoff_time=_aware(r[10]),
            actual_ft_home=r[3], actual_ft_away=r[4], actual_ht_home=r[5], actual_ht_away=r[6],
            actual_h2_home=r[7], actual_h2_away=r[8],
        ))
    return _Pool(by_league=by_league, loaded_at=time.monotonic())


async def _load_pool() -> _Pool:
    """Sonucu bilinen ve λ'sı hesaplanmış tüm aktif maçlar (as_of'tan bağımsız, 1 saat önbellek)."""
    global _pool
    if await _pool_fresh():
        return _pool
    async with _pool_lock:
        if await _pool_fresh():
            return _pool
        marker = await results_marker()
        known_at = func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at)
        stmt = select(
            Match.match_id, Match.team_lambda_home, Match.team_lambda_away,
            Match.actual_ft_home, Match.actual_ft_away,
            Match.actual_ht_home, Match.actual_ht_away,
            Match.actual_h2_home, Match.actual_h2_away,
            Match.league_name, Match.kickoff_time,
        ).where(
            Match.team_lambda_home.isnot(None), Match.team_lambda_away.isnot(None),
            Match.actual_ft_home.isnot(None), Match.actual_ft_away.isnot(None),
            Match.deleted_at.is_(None), Match.kickoff_time.isnot(None),
            known_at > Match.kickoff_time,
        )
        async with get_session() as session:
            rows = list((await session.execute(stmt)).all())
        _pool = await asyncio.to_thread(_build_pool, rows)
        _pool_watch.mark(marker)
        log.info("Pattern D (takım gücü) aday havuzu yüklendi: %d maç",
                 sum(len(v) for v in _pool.by_league.values()))
        return _pool


class _MatchedRow:
    """compute_stats için satır — benzerlik, liste sırası için taşınır."""

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


def nearest(candidates: list[_Candidate], target: tuple[float, float], *, cutoff: datetime,
            exclude_match_id: str | None, top_k: int) -> list[tuple[float, _Candidate]]:
    """log-λ uzayında en yakın top_k aday: (uzaklık, aday), yakından uzağa."""
    th, ta = math.log(target[0]), math.log(target[1])
    scored = (
        (math.hypot(c.log_h - th, c.log_a - ta), c)
        for c in candidates if c.kickoff_time <= cutoff and c.match_id != exclude_match_id
    )
    return heapq.nsmallest(top_k, scored, key=lambda item: item[0])


async def find_pattern_d_all_periods(
    target: tuple[float, float] | None,
    exclude_match_id: str | None = None,
    as_of: datetime | None = None,
    league_name: str | None = None,
    top_k: int = 200,
    min_matches: int = 1,
) -> tuple[PatternResult | None, PatternResult | None, PatternResult | None]:
    """Takım gücü (λ ev, λ dep) en yakın top_k maçın İY/2Y/MS istatistikleri.

    Args:
        target: maçın maç öncesi λ ev / λ dep (yoksa sonuç yok)
        exclude_match_id: analiz edilen maçın kendisi
        as_of: sadece bu andan 3 saat önce sonucu bilinen maçlar aday olur
        league_name: sadece aynı lig (başka lige düşülmez); None ise sonuç yok
        top_k: en yakın kaç maç
        min_matches: bu sayının altında aday varsa sonuç yok
    """
    if not target or not target[0] or not target[1] or not league_name:
        return None, None, None
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")

    pool = await _load_pool()
    hits = nearest(pool.by_league.get(league_name, []), target, cutoff=as_of - RESULT_KNOWN_DELAY,
                   exclude_match_id=exclude_match_id, top_k=top_k)
    if len(hits) < max(1, min_matches):
        log.debug("Pattern D: %d aday (minimum %d)", len(hits), min_matches)
        return None, None, None
    half_life = ANALYSIS.temporal_decay_half_life_years
    rows, weights = [], []
    for distance, c in hits:
        age_years = (as_of - c.kickoff_time).total_seconds() / (365.25 * 86400)
        weights.append(0.5 ** (max(0.0, age_years) / half_life) if half_life > 0 else 1.0)
        rows.append(_MatchedRow(c, math.exp(-distance)))
    return tuple(compute_stats(rows, period, weights=weights) for period in ("ht", "h2", "ft"))


