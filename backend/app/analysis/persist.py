"""Pattern sonuçlarını DB'ye kaydetmek için ortak yardımcı.

Pipeline ve API tarafı bu modülü kullanır — pattern hesaplamasının tek bir
doğru yeri olur, _result_to_row ve _do_analyze tek satırla pattern dolduran
dict alır.

Ayar parmak izi: her arşiv ailesinin (b/c/d) hesaplandığı ayarların kısa hash'i
matches.pattern_{b,c,d}_hash kolonlarına yazılır. Ayar değişince sadece o aile
"bayat" sayılır → tüm arşivi baştan hesaplamaya gerek kalmaz.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import update as sa_update

from app.analysis.league_filter import canonical_league_name
from app.analysis.pattern_b import find_pattern_b_matches
from app.analysis.pattern_c import find_pattern_c_adaptive
from app.analysis.pattern_d import IDF_CUTOFF, find_pattern_d_all_periods
from app.analysis.pattern_stats import PatternResult
from app.config import ANALYSIS
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)

FAMILIES: tuple[str, ...] = ("b", "c", "d")
PERIODS: tuple[str, ...] = ("ht", "h2", "ft")
PATTERN_B_MIN_MATCHES = 5

# Algoritma (kod) değişince ilgili ailenin sürümünü artır → o aile bayat sayılır.
# c3: adaptive minimumun altında sonuç yok. d3: min 10 eşleşme + IDF kesim tarihi (pattern_d.IDF_CUTOFF).
PATTERN_ALGO_VERSION = {"b": 2, "c": 3, "d": 3}


class PatternComputationError(RuntimeError):
    """An incomplete computation must never replace saved analysis."""


class StalePatternWrite(ValueError):
    """The source analysis changed while patterns were being computed."""


def pattern_keys(family: str) -> list[str]:
    return [f"pattern_{p}_{family}" for p in PERIODS]


def hash_string(hashes: dict[str, str | None]) -> str | None:
    """Aile parmak izlerini tek metne çevirir: 'b=…;c=…;d=…' (defter ve API aynı biçimi kullanır)."""
    return ";".join(f"{f}={hashes[f]}" for f in FAMILIES if hashes.get(f)) or None


def pattern_hashes() -> dict[str, str]:
    """Her ailenin sonucunu etkileyen ayarların kısa parmak izi."""
    a = ANALYSIS
    params = {
        "b": [PATTERN_ALGO_VERSION["b"], PATTERN_B_MIN_MATCHES, a.pattern_b_match_cap,
              a.temporal_decay_half_life_years],
        "c": [PATTERN_ALGO_VERSION["c"], a.pattern_c_tolerance, a.pattern_c_max_tolerance,
              a.pattern_c_tolerance_step, a.pattern_c_adaptive_min, a.pattern_c_match_cap,
              a.temporal_decay_half_life_years],
        "d": [PATTERN_ALGO_VERSION["d"], a.pattern_d_min_similarity, a.pattern_d_min_matches,
              IDF_CUTOFF.isoformat(), a.temporal_decay_half_life_years],
    }
    return {
        family: hashlib.sha1(json.dumps(values).encode()).hexdigest()[:12]
        for family, values in params.items()
    }


def stale_families(row: Match) -> list[str]:
    """Saklı parmak izi güncel ayarlarla uyuşmayan aileler."""
    if row.pattern_computed_at is None:
        return list(FAMILIES)
    current = pattern_hashes()
    return [f for f in FAMILIES if getattr(row, f"pattern_{f}_hash", None) != current[f]]


def pattern_as_of(analyzed_at: datetime, kickoff_time: datetime | None) -> datetime:
    """Pattern'in hangi andaki arşivle hesaplanacağı.

    Maç öncesi analizde analiz anı; maçtan sonra analiz edilen (arşiv) maçlarda
    kickoff anı — böylece hiçbir maç kendinden sonra oynanan maçları görmez.
    """
    if kickoff_time is not None and kickoff_time < analyzed_at:
        return kickoff_time
    return analyzed_at


def _dump(result: PatternResult | None) -> dict | None:
    if result is None:
        return None
    data = result.model_dump()
    data["matched_ids"] = list(result._matched_ids)
    if result._matched_sims:
        data["matched_sims"] = list(result._matched_sims)
    return data


async def compute_all_patterns(
    match_id: str,
    ht_scores: tuple[list, list, list],
    h2_scores: tuple[list, list, list],
    ft_scores: tuple[list, list, list],
    ft_ratios: dict | None,
    as_of: datetime,
    league_name: str | None = None,
    families: Iterable[str] = FAMILIES,
) -> dict[str, dict | None]:
    """İstenen pattern ailelerini tek seferde hesapla.

    exclude_match_id=match_id ile hesaplanır → analiz edilen maç kendi
    arşivine dahil edilmez. Lig filtresi katıdır: sadece aynı lig.

    Returns:
        {"pattern_ht_b": dict|None, ...} — sadece istenen ailelerin anahtarları.
        None yalnızca başarılı hesaplamada eşleşme yoksa döner; hatada yazma yapılmaz.
    """

    if as_of is None or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    families = tuple(f for f in FAMILIES if f in set(families))
    league = canonical_league_name(league_name) if league_name else None
    if not league or league == "?":
        # Katı lig kuralı: lig bilinmiyorsa tüm liglerde aramak yerine hiç eşleşme üretilmez
        # (eskiden None → filtresiz arama → başka liglerden eşleşmeler; Sprint 90.2).
        log.warning("Pattern hesaplanmadı [%s]: lig bilinmiyor", match_id)
        return {key: None for family in families for key in pattern_keys(family)}

    async def _b(period: str, s1, sx, s2) -> Optional[dict]:
        res = await find_pattern_b_matches(
            period, s1, sx, s2, min_matches=PATTERN_B_MIN_MATCHES,
            exclude_match_id=match_id, as_of=as_of,
            league_name=league,
            match_cap=ANALYSIS.pattern_b_match_cap,
            temporal_half_life=ANALYSIS.temporal_decay_half_life_years,
        )
        return _dump(res)

    async def _c_all() -> tuple[Optional[dict], Optional[dict], Optional[dict]]:
        if not ft_ratios:
            return None, None, None
        results = await find_pattern_c_adaptive(
            ft_ratios,
            min_matches=ANALYSIS.pattern_c_adaptive_min,
            base_tolerance=ANALYSIS.pattern_c_tolerance,
            max_tolerance=ANALYSIS.pattern_c_max_tolerance,
            tolerance_step=ANALYSIS.pattern_c_tolerance_step,
            exclude_match_id=match_id, as_of=as_of,
            league_name=league,
            match_cap=ANALYSIS.pattern_c_match_cap,
            temporal_half_life=ANALYSIS.temporal_decay_half_life_years,
        )
        return tuple(_dump(r) for r in results)

    async def _d_all() -> tuple[Optional[dict], Optional[dict], Optional[dict]]:
        if not ft_ratios:
            return None, None, None
        results = await find_pattern_d_all_periods(
            ft_ratios,
            min_similarity=ANALYSIS.pattern_d_min_similarity,
            exclude_match_id=match_id, as_of=as_of,
            league_name=league,
            min_matches=ANALYSIS.pattern_d_min_matches,
        )
        return tuple(_dump(r) for r in results)

    jobs: dict[str, object] = {}
    if "b" in families:
        jobs["b_ht"] = _b("ht", *ht_scores)
        jobs["b_h2"] = _b("h2", *h2_scores)
        jobs["b_ft"] = _b("ft", *ft_scores)
    if "c" in families:
        jobs["c"] = _c_all()
    if "d" in families:
        jobs["d"] = _d_all()

    outcomes = await asyncio.gather(*jobs.values(), return_exceptions=True)
    for name, outcome in zip(jobs, outcomes):
        if isinstance(outcome, asyncio.CancelledError):
            raise outcome
        if isinstance(outcome, Exception):
            log.warning("Pattern %s hesaplanamadı [%s]: %s", name, match_id, outcome)
            raise PatternComputationError(f"Pattern computation failed for {match_id}") from outcome
    done = dict(zip(jobs, outcomes))

    patterns: dict[str, dict | None] = {}
    if "b" in families:
        for period in PERIODS:
            patterns[f"pattern_{period}_b"] = done[f"b_{period}"]
    for family in ("c", "d"):
        if family in families:
            for period, value in zip(PERIODS, done[family]):
                patterns[f"pattern_{period}_{family}"] = value
    return patterns


def hash_columns(patterns: dict[str, dict | None]) -> dict[str, str]:
    """patterns içinde tam hesaplanmış ailelerin parmak izi kolonları."""
    current = pattern_hashes()
    return {
        f"pattern_{f}_hash": current[f]
        for f in FAMILIES
        if all(key in patterns for key in pattern_keys(f))
    }


async def update_match_patterns(match_id: str, patterns: dict[str, dict | None], *,
                                expected_analyzed_at: datetime | None,
                                computed_as_of: datetime | None = None) -> None:
    """matches satırının pattern kolonlarını (ve aile parmak izlerini) günceller.

    pattern_computed_at = hesaplamada kullanılan as_of → "maçtan önce hesaplandı"
    kanıtı recompute ile bozulmaz.
    """
    values: dict = {**patterns, **hash_columns(patterns)}
    values["pattern_computed_at"] = computed_as_of or expected_analyzed_at
    try:
        async with get_session() as session:
            result = await session.execute(
                sa_update(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None),
                                       Match.analyzed_at == expected_analyzed_at).values(**values)
            )
            if result.rowcount == 0:
                raise StalePatternWrite(f"Analysis changed or was deleted: {match_id}")
        log.debug("Pattern'ler DB'ye kaydedildi: %s", match_id)
    except Exception as exc:
        log.warning("Pattern'leri DB'ye yazamadık [%s]: %s", match_id, exc)
        raise
