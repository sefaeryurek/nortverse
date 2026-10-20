"""Canlı İY→MS modeli (live-ms-v1): COND × maç öncesi arşiv görüşü.

COND: aynı lig + aynı İY skoruyla biten önceki maçların MS dağılımı.
Örneklem < 30 ise aynı İY gol farkına, o da yetmezse tüm liglerdeki aynı farka düşülür.
Maç öncesi A1+A2+A3 havuzu lig ortalamasına oranlanır (LR) ve COND bununla çarpılır.

Ölçüm (1400 maç, 2023-26, sızıntısız): COND %58.0 / Brier .513, COND×LR %59.5 / Brier .504;
olasılık ≥0.70 olan tahminler ~%78 tutuyor.

Kalibrasyon (Sprint 89, backtest #3, α=0.5): eğitim <2025-07 / test ≥2025-07. Test döneminde gösterilen
ortalama %61.4, gerçekleşen %61.5 → zaten kalibre. Eğitimde kurulan isotonic düzeltme test Brier'ını üç
pazarda da kötüleştirdi (MS .2012→.2034, Ü2.5 .1873→.1874, KG .2332→.2334) → live-ms-v2 çıkarılmadı.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.analysis.freshness import ResultsWatch, results_marker
from app.analysis.league_filter import is_main_league
from app.analysis.league_priors import PRIOR_SEASON_DAYS, prior_from_counts
from app.analysis.pattern_b import RESULT_KNOWN_DELAY
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)

LIVE_RULE_VERSION = "live-ms-v1"
MIN_COND_N = 30
PREMATCH_K = 20.0
# Backtest (6071 maç, 2023-07..2026-10): α=0.5 Brier .5048 / α=1 .5079 / α=2 .5340; iki dönemde de 0.5 önde.
ALPHA = 0.5
TIER_HIGH = 0.70
TIER_MEDIUM = 0.55
MIN_ARCHIVE_N = 5
OUTCOMES = ("1", "X", "2")


@dataclass
class Counts:
    n1: int = 0
    nx: int = 0
    n2: int = 0
    over25: int = 0
    btts: int = 0
    # (İY ev, İY dep, MS ev, MS dep) → adet: her pazarın koşullu oranı buradan çözülür (live-arch-v2 kapısı)
    pairs: Counter = field(default_factory=Counter)

    @property
    def n(self) -> int:
        return self.n1 + self.nx + self.n2

    def add(self, ft_h: int, ft_a: int, sign: int = 1, ht: tuple[int, int] | None = None) -> None:
        if ht is not None:
            self.pairs[(ht[0], ht[1], ft_h, ft_a)] += sign
        if ft_h > ft_a:
            self.n1 += sign
        elif ft_h == ft_a:
            self.nx += sign
        else:
            self.n2 += sign
        self.over25 += sign * (ft_h + ft_a >= 3)
        self.btts += sign * (ft_h > 0 and ft_a > 0)

    def result_dist(self) -> dict[str, float]:
        """Laplace(0.5) — küçük örneklemde %0/%100 iddiası olmaz."""
        total = self.n + 1.5
        return {"1": (self.n1 + 0.5) / total, "X": (self.nx + 0.5) / total, "2": (self.n2 + 0.5) / total}


def _diff_key(h: int, a: int) -> int:
    return max(-3, min(3, h - a))


@lru_cache(maxsize=512)
def _in_reference_pool(league: str) -> bool:
    """Ortak "tüm ligler" havuzuna giren lig mi? (sadece 7 ana lig — Sprint 92)"""
    return is_main_league(league)


@dataclass
class CondTable:
    """İY skoruna koşullu MS sayaçları + lig prior'u. `add` ile artımlı büyür (backtest)."""

    cutoff: datetime
    prior_from: datetime
    by_score: dict[str, dict[tuple[int, int], Counts]] = field(default_factory=dict)
    by_diff: dict[str, dict[int, Counts]] = field(default_factory=dict)
    global_by_score: dict[tuple[int, int], Counts] = field(default_factory=dict)
    global_by_diff: dict[int, Counts] = field(default_factory=dict)
    prior: dict[str, Counts] = field(default_factory=dict)

    def add(self, league: str, ht_h: int, ht_a: int, ft_h: int, ft_a: int, kickoff: datetime) -> None:
        key, diff = (ht_h, ht_a), _diff_key(ht_h, ht_a)
        self.by_score.setdefault(league, {}).setdefault(key, Counts()).add(ft_h, ft_a, ht=key)
        self.by_diff.setdefault(league, {}).setdefault(diff, Counts()).add(ft_h, ft_a)
        if _in_reference_pool(league):
            # "Tüm ligler" yedeği sadece ana liglerden: gölgedeki yeni ligler ana liglerin oranlarını kaydırmasın
            self.global_by_score.setdefault(key, Counts()).add(ft_h, ft_a, ht=key)
            self.global_by_diff.setdefault(diff, Counts()).add(ft_h, ft_a)
        if kickoff >= self.prior_from:
            self.prior.setdefault(league, Counts()).add(ft_h, ft_a)

    def cond(self, league: str, ht: tuple[int, int]) -> tuple[str, Counts]:
        same = self.by_score.get(league, {}).get(ht)
        if same and same.n >= MIN_COND_N:
            return "score", same
        diff = _diff_key(*ht)
        by_diff = self.by_diff.get(league, {}).get(diff)
        if by_diff and by_diff.n >= MIN_COND_N:
            return "diff", by_diff
        return "global_diff", self.global_by_diff.get(diff, Counts())

    def goal_counts(self, league: str, ht: tuple[int, int]) -> Counts:
        same = self.by_score.get(league, {}).get(ht)
        if same and same.n >= MIN_COND_N:
            return same
        return self.global_by_score.get(ht, Counts())

    def _league_prior(self, league: str):
        """Lig ortalaması — `league_priors.prior_from_counts` (tüm modüllerle aynı formül)."""
        c = self.prior.get(league, Counts())
        return prior_from_counts(c.n1, c.nx, c.n2, c.over25, c.btts)

    def league_prior(self, league: str) -> dict[str, float]:
        return self._league_prior(league).result

    def league_goal_prior(self, league: str) -> dict[str, float]:
        """Lig son 3 sezon MS Üst 2.5 ve KG oranı (Laplace 0.5)."""
        prior = self._league_prior(league)
        return {"over25": prior.over25, "btts": prior.btts}


def prematch_posterior(
    blobs: list[dict | None], prior: dict[str, float], k: float = PREMATCH_K,
) -> tuple[dict[str, float], float] | None:
    """A1+A2+A3 havuzlanmış 1/X/2 olasılığı, Dirichlet(k) ile lig prior'una çekilmiş."""
    pooled = {o: 0.0 for o in OUTCOMES}
    total = 0.0
    for blob in blobs:
        if not blob or not blob.get("match_count"):
            continue
        mc = float(blob["match_count"])
        total += mc
        pooled["1"] += mc * blob.get("result_1_pct", 0.0) / 100
        pooled["X"] += mc * blob.get("result_x_pct", 0.0) / 100
        pooled["2"] += mc * blob.get("result_2_pct", 0.0) / 100
    if total <= 0:
        return None
    return {o: (pooled[o] + k * prior[o]) / (total + k) for o in OUTCOMES}, total


def _tier(prob: float, n: int) -> str:
    if n < MIN_COND_N:
        return "insufficient"
    if prob >= TIER_HIGH:
        return "high"
    if prob >= TIER_MEDIUM:
        return "medium"
    return "low"


def _binary(counts: Counts, hits: int, yes: str, no: str) -> dict:
    p_yes = (hits + 0.5) / (counts.n + 1.0)
    pick, prob = (yes, p_yes) if p_yes >= 0.5 else (no, 1 - p_yes)
    return {"applicable": True, "pick": pick, "prob": round(prob, 4), "n": counts.n,
            "tier": _tier(prob, counts.n)}


def predict_live(
    table: CondTable, league: str, ht: tuple[int, int],
    pattern_blobs: list[dict | None], alpha: float = ALPHA,
) -> dict:
    """Tek maç için canlı tahmin: MS 1X2 (+ uygunsa MS Ü2.5 ve KG)."""
    level, cond_counts = table.cond(league, ht)
    cond = cond_counts.result_dist()
    prior = table.league_prior(league)
    posterior = prematch_posterior(pattern_blobs, prior)
    if posterior is not None:
        post, pooled_n = posterior
        lr = {o: post[o] / prior[o] for o in OUTCOMES}
        raw = {o: cond[o] * lr[o] ** alpha for o in OUTCOMES}
        norm = sum(raw.values())
        probs = {o: raw[o] / norm for o in OUTCOMES}
    else:
        post, pooled_n, lr, probs = None, 0.0, None, dict(cond)
    pick = max(OUTCOMES, key=lambda o: probs[o])
    cond_pick = max(OUTCOMES, key=lambda o: cond[o])
    ms = {
        "probs": {o: round(p, 4) for o, p in probs.items()},
        "pick": pick,
        "prob": round(probs[pick], 4),
        "tier": _tier(probs[pick], cond_counts.n),
        "n": cond_counts.n,
        "cond_level": level,
        "ht_baseline": {"probs": {o: round(p, 4) for o, p in cond.items()},
                        "pick": cond_pick, "prob": round(cond[cond_pick], 4)},
        "prematch": None if post is None else {
            "probs": {o: round(p, 4) for o, p in post.items()},
            "pooled_n": round(pooled_n, 1),
            "lr": {o: round(v, 4) for o, v in lr.items()},
        },
        "prior": {o: round(p, 4) for o, p in prior.items()},
    }
    goals = table.goal_counts(league, ht)
    over25 = ({"applicable": False, "reason": "already_over"} if sum(ht) >= 3
              else _binary(goals, goals.over25, "over", "under"))
    btts = ({"applicable": False, "reason": "already_both"} if ht[0] > 0 and ht[1] > 0
            else _binary(goals, goals.btts, "yes", "no"))
    return {"rule_version": LIVE_RULE_VERSION, "ht": {"home": ht[0], "away": ht[1]},
            "ms": ms, "over25": over25, "btts": btts}


# ─── Günlük COND önbelleği ──────────────────────────────────────────────────

_table: CondTable | None = None
_table_built_at: float = 0.0
_lock = asyncio.Lock()
TABLE_TTL_SECONDS = 6 * 3600


async def build_cond_table(as_of: datetime) -> CondTable:
    cutoff = as_of - RESULT_KNOWN_DELAY
    known_at = func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at)
    stmt = select(
        Match.league_name, Match.actual_ht_home, Match.actual_ht_away,
        Match.actual_ft_home, Match.actual_ft_away, Match.kickoff_time,
    ).where(
        Match.deleted_at.is_(None),
        Match.actual_ft_home.isnot(None), Match.actual_ft_away.isnot(None),
        Match.actual_ht_home.isnot(None), Match.actual_ht_away.isnot(None),
        Match.kickoff_time <= cutoff,
        known_at > Match.kickoff_time,
    )
    async with get_session() as session:
        rows = (await session.execute(stmt)).all()

    def _build() -> CondTable:
        table = CondTable(cutoff=cutoff, prior_from=as_of - timedelta(days=PRIOR_SEASON_DAYS))
        for league, ht_h, ht_a, ft_h, ft_a, kickoff in rows:
            if ht_h > ft_h or ht_a > ft_a or league is None:
                continue
            kickoff = kickoff if kickoff.tzinfo else kickoff.replace(tzinfo=timezone.utc)
            table.add(league, ht_h, ht_a, ft_h, ft_a, kickoff)
        return table

    table = await asyncio.to_thread(_build)
    log.info("Canlı COND tablosu kuruldu: %d maç (kesim %s)", len(rows), cutoff.isoformat())
    return table


_table_watch = ResultsWatch()


async def _table_fresh() -> bool:
    return (_table is not None and time.monotonic() - _table_built_at < TABLE_TTL_SECONDS
            and not await _table_watch.stale())


async def get_cond_table() -> CondTable:
    """6 saatte bir ya da yeni sonuç gelince (en fazla 5 dk'da bir kontrol) kurulur.

    Sızıntısız: kesim = kuruluş anı − 3 saat.
    """
    global _table, _table_built_at
    if await _table_fresh():
        return _table
    async with _lock:
        if not await _table_fresh():
            marker = await results_marker()
            _table = await build_cond_table(datetime.now(timezone.utc))
            _table_built_at = time.monotonic()
            _table_watch.mark(marker)
    return _table


def invalidate_cond_table() -> None:
    global _table, _table_built_at
    _table = None
    _table_built_at = 0.0
    _table_watch.marker = None
