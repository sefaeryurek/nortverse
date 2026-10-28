"""Ana Pazar Özeti v3 — GÖLGE (Sprint 94 H1, K7).

v2 her pazarda tek bir arşivin en sık seçimini "kazanan" sayıyor ve sıklığı olasılık gibi gösteriyordu:
1.460 tekil kararda gösterilen %54,5 → gerçekleşen %48,1 (beklentinin altında). v3 aynı pazarlarda kazananı
maç öncesi takım gücü modelinin (v5 Dixon-Coles skor ızgarası) olasılığından seçer; gösterilen = model olasılığı.
A1/A2/A3'ün aynı seçim için sıklıkları ayrıntıda karşılaştırma için tutulur. Sadece maç sonu (İY'ye bağlı
pazarlar — İY/MS — ızgaradan çözülemez, atlanır). Ekranda yok; pazar başına ≥100 karar sonrası karne.
"""

from __future__ import annotations

import hashlib
import json

from app.analysis.market_catalog import SUMMARY_MARKET_KEYS, get_market
from app.analysis.market_resolver import _ScoreRow
from app.analysis.pattern_stats import compute_stats

MARKET_SUMMARY_SHADOW_VERSION = "market-summary-v3"
PARAMS = {
    "source": "v5 dixon-coles score grid", "period": "ft", "selection": "argmax_model_probability",
    "skip": "markets needing first-half score", "min_cell_prob": 1e-7,
}
_ARCHIVES = (("a1", "b"), ("a2", "c"), ("a3", "d"))


def fingerprint() -> str:
    from app.analysis.live_poisson import team_model_fingerprint
    from app.analysis.prematch_v5 import rule_params_fingerprint as v5_fingerprint

    payload = {**PARAMS, "markets": list(SUMMARY_MARKET_KEYS), "team_model": team_model_fingerprint(),
               "v5": v5_fingerprint()}
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def _markets() -> list:
    return [spec for spec in map(get_market, SUMMARY_MARKET_KEYS) if spec.active_in("ft") and not spec.ft_only]


def market_probabilities(grid: list[tuple[int, int, float]]) -> dict[str, dict[str, float]]:
    """Skor ızgarasından her pazarın her seçiminin olasılığı (çözücüyle aynı tanım: compute_stats alanı %100)."""
    markets = _markets()
    out = {spec.key: {code: 0.0 for _, code in spec.fields} for spec in markets}
    total = 0.0
    for h, a, p in grid:
        if p < PARAMS["min_cell_prob"]:
            continue
        total += p
        row = _ScoreRow(actual_ht_home=None, actual_ht_away=None, actual_h2_home=None, actual_h2_away=None,
                        actual_ft_home=h, actual_ft_away=a)
        stats = compute_stats([row], "ft")
        if stats is None:
            continue
        for spec in markets:
            for field, code in spec.fields:
                if getattr(stats, field) >= 99.95:
                    out[spec.key][code] += p
    return {k: {c: v / total for c, v in sel.items()} for k, sel in out.items()} if total else {}


def ledger_rows(grid: list[tuple[int, int, float]] | None, patterns: dict | None, common: dict) -> list[dict]:
    if not grid:
        return []
    params = fingerprint()
    rows = []
    for key, probs in market_probabilities(grid).items():
        if not probs:
            continue
        selection, prob = max(probs.items(), key=lambda kv: kv[1])
        spec = get_market(key)
        field = spec.field_for(selection)
        archive_pct = {}
        for short, family in _ARCHIVES:
            blob = (patterns or {}).get(f"pattern_ft_{family}")
            if isinstance(blob, dict) and blob.get("match_count"):
                archive_pct[short] = blob.get(field)
        rows.append({
            **common, "source": "market_summary", "rule_version": MARKET_SUMMARY_SHADOW_VERSION,
            "period": "ft", "market": key, "selection": selection, "archive": None,
            "prob_shown_bp": round(prob * 10000), "confidence_tier": "medium",
            "details": {"shadow": True, "probs": {k: round(v, 4) for k, v in probs.items()},
                        "archive_pct": archive_pct, "params": params},
        })
    return rows
