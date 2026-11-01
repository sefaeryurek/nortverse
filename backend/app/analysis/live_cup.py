"""Avrupa kupaları canlı gölge kuralı live-cup-cond-v1 (Sprint 94 P4, K17 seçenek B).

Kupa maçlarında takım gücü modeli yok (takımlar farklı liglerden; ligler arası model ayrı ve büyük iş). En düşük
riskli başlangıç: devre arasında "aynı kupa + aynı İY skoru" ile biten lig/grup aşaması maçlarının 90 dakika
sonuçları (COND). Kural live-arch-v2'nin COND kapısıyla aynı: 6 pazar, ≥30 maç, ≥%85. Kupada ≥30 maç yoksa
üç kupanın ortak geçmişi. Veri `cup_results` tablosundan (`build-cup-archive`); ana liglerin hiçbir havuzuna
karışmaz.

GÖLGEDE: ekranda yok, sadece deftere (`details.cup`). Riskler: rotasyon, iki ayaklı eşleşmelerde rövanş (eleme
turları arşive alınmıyor ama canlıda onlara da karar yazılır — karnede `round` ile ayrılır), az örneklem.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone

from app.analysis.league_filter import TRACKED_CUPS
from app.analysis.live_archive import RULE_PARAMS as ARCH_PARAMS
from app.analysis.live_archive import cond_probability, market_decided
from app.analysis.live_model import CondTable
from app.analysis.market_catalog import get_market
from app.analysis.pattern_b import RESULT_KNOWN_DELAY

log = logging.getLogger(__name__)

LIVE_CUP_SHADOW_VERSION = "live-cup-cond-v1"
POOLED = "UEFA kupaları (ortak)"
RULE_PARAMS = {
    "cups": sorted(TRACKED_CUPS),
    "markets": ARCH_PARAMS["markets"],
    "threshold_pct": 85.0,
    "min_n": ARCH_PARAMS["cond_min_n"],
    "fallback": "three cups pooled",
    "window_years": 10,
    "archive_stages": "league/group stage only",
}


def shadow_params_fingerprint() -> str:
    return hashlib.sha1(json.dumps(RULE_PARAMS, sort_keys=True).encode()).hexdigest()[:12]


def build_table(rows, as_of: datetime) -> CondTable:
    """`rows`: (competition, ht_home, ht_away, ft_home, ft_away, kickoff). Sadece as_of − 3 saatten önce bitenler."""
    cutoff = as_of - RESULT_KNOWN_DELAY
    table = CondTable(cutoff=cutoff, prior_from=cutoff - timedelta(days=3 * 365),
                      window_from=as_of - timedelta(days=round(365.25 * RULE_PARAMS["window_years"])))
    for competition, ht_h, ht_a, ft_h, ft_a, kickoff in rows:
        if kickoff is None or kickoff > cutoff:
            continue
        for key in (competition, POOLED):
            table.add(key, ht_h, ht_a, ft_h, ft_a, kickoff)
    return table


def decide(table: CondTable, cup: str, ht: tuple[int, int]) -> list[dict]:
    """Pazar başına en olası seçim ≥%85 ise karar. Önce aynı kupa, ≥30 maç yoksa üç kupa ortak."""
    picks = []
    for period, market in RULE_PARAMS["markets"]:
        if market_decided(period, market, tuple(ht)):
            continue
        best = None
        for key, level in ((cup, "cup"), (POOLED, "pooled")):
            options = {}
            for _field, code in get_market(market).fields:
                cond = cond_probability(table, key, ht, period, market, code)
                if cond is not None:
                    options[code] = cond
            if options:
                code, cond = max(options.items(), key=lambda kv: kv[1]["pct"])
                best = {"period": period, "market": market, "selection": code, "pct": cond["pct"],
                        "n": cond["n"], "level": level,
                        "options": {c: o["pct"] for c, o in options.items()}}
                break
        if best and best["pct"] >= RULE_PARAMS["threshold_pct"]:
            picks.append(best)
    return picks


def ledger_rows(picks: list[dict], common: dict, *, cup: str, late: bool = False) -> list[dict]:
    params = shadow_params_fingerprint()
    return [{
        **common, "source": "live_ht", "rule_version": LIVE_CUP_SHADOW_VERSION,
        "period": p["period"], "market": p["market"], "selection": p["selection"],
        "prob_shown_bp": round(p["pct"] * 100), "sample_n": p["n"], "confidence_tier": "high",
        "details": {"shadow": True, "cup": cup, "cond_level": p["level"], "cond_n": p["n"],
                    "options": p["options"], "params": params, "late": late},
    } for p in picks]


_TTL = 6 * 3600.0
_cache: tuple[float, CondTable] | None = None


async def get_cup_table() -> CondTable:
    """Arşiv yavaş değişir (günde bir pipeline günceller) → 6 saat önbellek."""
    global _cache
    if _cache is not None and time.monotonic() - _cache[0] < _TTL:
        return _cache[1]
    from sqlalchemy import select

    from app.db.connection import get_session
    from app.db.models import CupResult

    async with get_session() as session:
        rows = (await session.execute(select(
            CupResult.competition, CupResult.ht_home, CupResult.ht_away, CupResult.ft_home, CupResult.ft_away,
            CupResult.kickoff_time,
        ))).all()
    table = build_table(rows, datetime.now(timezone.utc))
    _cache = (time.monotonic(), table)
    return table
