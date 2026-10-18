"""Canlı İY arşiv görünümü (live-arch-v1).

Maçın A1/A2/A3 eşleşen arşiv maçlarından İY skoru aynı bitenler alınır; her arşiv için ayrı
ve üçünün birleşimi (Genel, tekrarsız) için pazar oranları hesaplanır.

- İY skorunun zaten kesinleştirdiği pazarlar (ör. İY 2-1'de MS KG Var) gösterilmez.
- Oranı ≥%85 olan seçimler "öne çıkanlar"dır ve devre arasında deftere yazılır.
- Örneklem 5 maçtan azsa öne çıkan seçim "riskli" işaretlenir (yine gösterilir ve kaydedilir).

Arşiv üyelikleri maç öncesi (kickoff) hesaplanmış `matched_ids`'ten gelir → sızıntısız.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache

from app.analysis.market_catalog import get_market
from app.analysis.market_resolver import resolve
from app.analysis.pattern_stats import compute_stats

LIVE_ARCHIVE_RULE_VERSION = "live-arch-v1"
RULE_PARAMS = {
    "threshold_pct": 85.0,
    "risky_below_n": 5,
    "markets": [
        ["ft", "result"], ["ft", "dc"], ["ft", "ou_15"], ["ft", "ou_25"], ["ft", "ou_35"], ["ft", "kg"],
        ["h2", "result"], ["h2", "ou_05"], ["h2", "ou_15"], ["h2", "kg"],
    ],
}
THRESHOLD_PCT = RULE_PARAMS["threshold_pct"]
RISKY_BELOW_N = RULE_PARAMS["risky_below_n"]
LIVE_MARKETS: tuple[tuple[str, str], ...] = tuple((p, m) for p, m in RULE_PARAMS["markets"])
SOURCES = (("b", "a1", "A1"), ("c", "a2", "A2"), ("d", "a3", "A3"))
GENERAL = "genel"


def rule_params_fingerprint() -> str:
    return hashlib.sha1(json.dumps(RULE_PARAMS, sort_keys=True).encode()).hexdigest()[:12]


@dataclass(frozen=True)
class ArchiveMatch:
    """Eşleşen arşiv maçının skorları (compute_stats satırı)."""

    match_id: str
    actual_ht_home: int
    actual_ht_away: int
    actual_ft_home: int
    actual_ft_away: int

    @property
    def actual_h2_home(self) -> int:
        return self.actual_ft_home - self.actual_ht_home

    @property
    def actual_h2_away(self) -> int:
        return self.actual_ft_away - self.actual_ht_away


@lru_cache(maxsize=4096)
def market_decided(period: str, market: str, ht: tuple[int, int]) -> bool:
    """İY skoru bu pazarın sonucunu zaten belirlediyse True (2. yarı ne olursa olsun aynı sonuç)."""
    if period != "ft":
        return False
    code = get_market(market).fields[0][1]
    outcomes = {
        resolve("ft", market, code, ht, (ht[0] + h, ht[1] + a))
        for h in range(0, 9) for a in range(0, 9)
    }
    return len(outcomes) == 1


def market_cells(rows: list[ArchiveMatch], ht: tuple[int, int]) -> list[dict]:
    """Her (periyot, pazar) için en yüksek seçim ve tüm seçimlerin oranları."""
    if not rows:
        return []
    stats = {period: compute_stats(rows, period) for period in ("ft", "h2")}
    cells = []
    for period, market in LIVE_MARKETS:
        result = stats[period]
        if result is None or market_decided(period, market, tuple(ht)):
            continue
        spec = get_market(market)
        values = [(code, round(float(getattr(result, field)), 1)) for field, code in spec.fields]
        best_code, best_pct = values[0]
        for code, value in values[1:]:
            if value > best_pct:
                best_code, best_pct = code, value
        cells.append({
            "period": period, "market": market, "selection": best_code, "pct": best_pct,
            "options": dict(values),
        })
    return cells


def build_view(rows_by_source: dict[str, list[ArchiveMatch]], ht: tuple[int, int]) -> dict:
    """A1/A2/A3 + Genel tablo ve ≥%85 öne çıkanlar."""
    general: dict[str, ArchiveMatch] = {}
    for _, short, _ in SOURCES:
        for row in rows_by_source.get(short, []):
            general.setdefault(row.match_id, row)
    sources = []
    for short, label, rows in (
        *((s, lbl, rows_by_source.get(s, [])) for _, s, lbl in SOURCES),
        (GENERAL, "Genel", list(general.values())),
    ):
        n = len(rows)
        sources.append({
            "archive": short, "label": label, "n": n, "risky": 0 < n < RISKY_BELOW_N,
            "cells": market_cells(rows, ht),
        })
    highlights = [
        {**cell, "archive": src["archive"], "label": src["label"], "n": src["n"], "risky": src["risky"]}
        for src in sources for cell in src["cells"] if cell["pct"] >= THRESHOLD_PCT
    ]
    highlights.sort(key=lambda h: (h["risky"], -h["pct"], -h["n"]))
    return {
        "rule_version": LIVE_ARCHIVE_RULE_VERSION, "ht": {"home": ht[0], "away": ht[1]},
        "threshold_pct": THRESHOLD_PCT, "risky_below_n": RISKY_BELOW_N,
        "sources": sources, "highlights": highlights,
    }


def ht_filtered_rows(blobs: dict[str, dict | None], results: dict[str, tuple], ht: tuple[int, int]
                     ) -> dict[str, list[ArchiveMatch]]:
    """Ailelerin `matched_ids`'inden İY skoru aynı bitenler. results: id → (ht_h, ht_a, ft_h, ft_a)."""
    out: dict[str, list[ArchiveMatch]] = {}
    for family, short, _ in SOURCES:
        rows = []
        for mid in (blobs.get(family) or {}).get("matched_ids") or []:
            r = results.get(str(mid))
            if r is None or r[0] is None or r[2] is None or (r[0], r[1]) != tuple(ht):
                continue
            if r[0] > r[2] or r[1] > r[3]:
                continue
            rows.append(ArchiveMatch(str(mid), r[0], r[1], r[2], r[3]))
        out[short] = rows
    return out


def ledger_rows(view: dict, common: dict) -> list[dict]:
    """Öne çıkan her seçim için defter satırı (Genel → archive NULL)."""
    rows = []
    for h in view["highlights"]:
        rows.append({
            **common, "source": "live_ht", "rule_version": LIVE_ARCHIVE_RULE_VERSION,
            "period": h["period"], "market": h["market"], "selection": h["selection"],
            "archive": None if h["archive"] == GENERAL else h["archive"],
            "prob_shown_bp": round(h["pct"] * 100), "sample_n": h["n"] or None,
            "confidence_tier": "insufficient" if h["risky"] else "high",
            "details": {"risky": h["risky"], "label": h["label"], "options": h["options"],
                        "params": rule_params_fingerprint()},
        })
    return rows


# ─── DB yükleme + kısa önbellek (WS her 15 sn'de tüm canlı maçları ister) ──────

_VIEW_TTL = 600.0
_view_cache: dict[tuple, tuple[float, dict]] = {}


async def load_view(match_id: str, blobs: dict[str, dict | None], ht: tuple[int, int],
                    *, with_matches: bool = False) -> dict:
    """Maçın canlı arşiv görünümü. with_matches=True: her kaynağın maç listesi (en yeni önce)."""
    import time

    from sqlalchemy import select

    from app.db.connection import get_session
    from app.db.models import Match

    key = (match_id, tuple(ht), with_matches)
    cached = _view_cache.get(key)
    if cached is not None and time.monotonic() - cached[0] < _VIEW_TTL:
        return cached[1]
    ids = {str(i) for blob in blobs.values() for i in ((blob or {}).get("matched_ids") or [])}
    info: dict[str, tuple] = {}
    if ids:
        async with get_session() as session:
            result = await session.execute(
                select(Match.match_id, Match.actual_ht_home, Match.actual_ht_away,
                       Match.actual_ft_home, Match.actual_ft_away,
                       Match.home_team, Match.away_team, Match.kickoff_time)
                .where(Match.match_id.in_(ids), Match.deleted_at.is_(None))
            )
            info = {r[0]: tuple(r[1:]) for r in result.all()}
    rows_by_source = ht_filtered_rows(blobs, {k: v[:4] for k, v in info.items()}, ht)
    view = build_view(rows_by_source, ht)
    if with_matches:
        sims = {
            short: dict(zip([str(i) for i in (blobs.get(family) or {}).get("matched_ids") or []],
                            (blobs.get(family) or {}).get("matched_sims") or []))
            for family, short, _ in SOURCES
        }
        for src in view["sources"]:
            rows = (rows_by_source.get(src["archive"]) if src["archive"] != GENERAL
                    else list({r.match_id: r for s in rows_by_source.values() for r in s}.values()))
            matches = []
            for r in rows:
                home, away, kickoff = info[r.match_id][4:7]
                ft = (r.actual_ft_home, r.actual_ft_away)
                matches.append({
                    "match_id": r.match_id, "home_team": home, "away_team": away,
                    "kickoff_time": kickoff.isoformat() if kickoff else None,
                    "ht": f"{r.actual_ht_home}-{r.actual_ht_away}", "ft": f"{ft[0]}-{ft[1]}",
                    "result": "1" if ft[0] > ft[1] else "X" if ft[0] == ft[1] else "2",
                    "similarity": sims.get(src["archive"], {}).get(r.match_id),
                })
            matches.sort(key=lambda m: m["kickoff_time"] or "", reverse=True)
            src["matches"] = matches
    if len(_view_cache) > 500:
        _view_cache.clear()
    _view_cache[key] = (time.monotonic(), view)
    return view
