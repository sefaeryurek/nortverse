"""Lig ortalamaları — tüm modüllerin tek kaynağı.

Tanım: o ligde son 3 sezonda (as_of − 3 yıl … as_of − 3 saat) oynanmış, sonucu maçtan sonra
kaydedilmiş maçların MS 1/X/2, Üst 2.5 ve KG oranı; Laplace(0.5) yumuşatmalı.
Canlı model (CondTable), maç öncesi v4, Pattern geçmişi, backtest ve ensemble aynı formülü kullanır.
Ligde hiç maç yoksa tüm liglerin toplamına düşülür; DB boşsa genel bir varsayılan döner.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.analysis.league_filter import canonical_league_name
from app.analysis.pattern_b import RESULT_KNOWN_DELAY

PRIOR_SEASON_DAYS = 3 * 365
OUTCOMES = ("1", "X", "2")

# DB'de hiç sonuç yokken (boş kurulum, testler) kullanılan genel varsayılan.
DEFAULT_RATES: dict[str, float] = {"1": 45.3, "X": 24.9, "2": 29.8, "ou25": 52.7, "btts": 53.2}


@dataclass(frozen=True)
class LeaguePrior:
    n: int
    result: dict[str, float]  # olasılık (0-1)
    over25: float
    btts: float

    def as_pct_rates(self) -> dict[str, float]:
        """Değerlendirme modülünün beklediği yüzde biçimi."""
        return {
            "1": self.result["1"] * 100, "X": self.result["X"] * 100, "2": self.result["2"] * 100,
            "ou25": self.over25 * 100, "btts": self.btts * 100,
        }


def prior_from_counts(n1: int, nx: int, n2: int, over25: int, btts: int) -> LeaguePrior:
    """Laplace(0.5): küçük örneklemde %0/%100 iddiası olmaz."""
    n = n1 + nx + n2
    total = n + 1.5
    return LeaguePrior(
        n=n,
        result={"1": (n1 + 0.5) / total, "X": (nx + 0.5) / total, "2": (n2 + 0.5) / total},
        over25=(over25 + 0.5) / (n + 1.0),
        btts=(btts + 0.5) / (n + 1.0),
    )


@dataclass
class PriorBook:
    """Bir as_of anındaki tüm lig ortalamaları (lig adı kanonik)."""

    as_of: datetime | None
    leagues: dict[str, LeaguePrior] = field(default_factory=dict)
    overall: LeaguePrior | None = None

    def get(self, league_name: str | None) -> LeaguePrior | None:
        if league_name:
            found = self.leagues.get(canonical_league_name(league_name))
            if found is not None and found.n > 0:
                return found
        return self.overall if self.overall is not None and self.overall.n > 0 else None

    def rates(self, league_name: str | None) -> dict[str, float]:
        prior = self.get(league_name)
        return prior.as_pct_rates() if prior is not None else dict(DEFAULT_RATES)


def book_from_counts(as_of: datetime | None, rows: list[tuple]) -> PriorBook:
    """rows: (lig, n1, nx, n2, over25, btts)."""
    merged: dict[str, list[int]] = {}
    for league, *counts in rows:
        if not league:
            continue
        acc = merged.setdefault(canonical_league_name(league), [0, 0, 0, 0, 0])
        for i, value in enumerate(counts):
            acc[i] += int(value or 0)
    # Genel değer (ligde veri yoksa yedek) sadece ana liglerden: gölgedeki yeni ligler bunu kaydırmasın.
    from app.analysis.league_filter import is_main_league

    reference = [c for league, c in merged.items() if is_main_league(league)] or list(merged.values())
    totals = [sum(c[i] for c in reference) for i in range(5)]
    return PriorBook(
        as_of=as_of,
        leagues={league: prior_from_counts(*c) for league, c in merged.items()},
        overall=prior_from_counts(*totals) if merged else None,
    )


async def _query_book(as_of: datetime) -> PriorBook:
    from app.db.connection import get_session
    from app.db.models import Match

    known_at = func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at)
    ft_h, ft_a = Match.actual_ft_home, Match.actual_ft_away
    stmt = select(
        Match.league_name,
        func.count().filter(ft_h > ft_a),
        func.count().filter(ft_h == ft_a),
        func.count().filter(ft_h < ft_a),
        func.count().filter(ft_h + ft_a >= 3),
        func.count().filter((ft_h > 0) & (ft_a > 0)),
    ).where(
        # CondTable ile aynı süzgeç: İY ve MS dolu, İY ≤ MS, sonuç maçtan sonra bilinmiş.
        Match.deleted_at.is_(None), Match.model_only.is_(False),
        ft_h.isnot(None), ft_a.isnot(None),
        Match.actual_ht_home.isnot(None), Match.actual_ht_away.isnot(None),
        Match.actual_ht_home <= ft_h, Match.actual_ht_away <= ft_a,
        Match.league_name.isnot(None),
        Match.kickoff_time >= as_of - timedelta(days=PRIOR_SEASON_DAYS),
        Match.kickoff_time <= as_of - RESULT_KNOWN_DELAY,
        known_at > Match.kickoff_time,
    ).group_by(Match.league_name)
    async with get_session() as session:
        rows = (await session.execute(stmt)).all()
    return book_from_counts(as_of, [tuple(r) for r in rows])


def istanbul_day_start(moment: datetime) -> datetime:
    """Maçın İstanbul gününün başlangıcı — günlük değerlendirmede o günün maçları prior'a girmez."""
    from app.config import ISTANBUL_TZ

    local = moment.astimezone(ISTANBUL_TZ)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


_cache: OrderedDict[str, PriorBook] = OrderedDict()
_cache_lock = asyncio.Lock()
_CACHE_MAX = 64


async def load_prior_book(as_of: datetime) -> PriorBook:
    """as_of anındaki lig ortalamaları (aynı an için süreç içinde önbellekli)."""
    key = as_of.isoformat()
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    async with _cache_lock:
        if key not in _cache:
            _cache[key] = await _query_book(as_of)
            while len(_cache) > _CACHE_MAX:
                _cache.popitem(last=False)
    return _cache[key]
