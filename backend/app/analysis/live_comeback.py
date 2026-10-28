"""Canlı "güçlü takım geride" kararları — live-comeback-v1 (Sprint 94 Faz O3, GÖLGE).

Fikir (denetim 28 Ekim): İY'de 1 farkla geride olan takımın maç öncesi gol beklentisi rakibinin ≥2,2 katıysa
(takım gücü λ'ları, sızıntısız) geri dönüş oranı belirgin yükselir. Ölçüm (ana ligler, `matches.team_lambda_*`):

| dönem | maç | geride kazanır | kaybetmez | 2Y gol atar |
|---|---|---|---|---|
| 2023-07 öncesi | 429 | %32,6 | %60,6 | %75,5 |
| 2023-07 sonrası | 109 | %43,1 | %70,6 | %79,8 |
(λ oranı <0,8: 1.227 maç, %6,8 / %24,9 / %45,5)

Kalibrasyon (29 Ekim, backtest #14 live-2h): bu dilimde geride olan takımın 2Y gol kararı %78,5 gösterip %79,1
tuttu (91 karar) → model bu dilimde güvenilir. Gölge kararlar:
- 2Y gol (geride olan takım): eşik live-2h'nin 70'i yerine 65
- Çifte şans "kaybetmez" (geride olan takım): eşiksiz, "orta güven" — modelin gösterdiği olasılığın kalibrasyonu ölçülür
Olasılıklar live-poisson son skor ızgarasından. Ekranda yok; 100 tekil karar sonra karne.
"""

from __future__ import annotations

import hashlib
import json

from app.analysis import live_poisson
from app.analysis.live_archive import _pair_hit

LIVE_COMEBACK_SHADOW_VERSION = "live-comeback-v1"
RULE_PARAMS = {
    "ht_deficit": 1,
    "min_lambda_ratio": 2.2,
    "h2_goal_min_pct": 65.0,
}


def shadow_params_fingerprint() -> str:
    payload = {"team_model": live_poisson.team_model_fingerprint(), **RULE_PARAMS}
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def _prob(grid, period: str, market: str, selection: str) -> float:
    return round(100 * sum(p for pair, p in grid if _pair_hit(period, market, selection, pair)), 1)


def decide(dist: dict | None, ht: tuple[int, int]) -> list[dict]:
    """`dist`: `live_poisson.final_grid` çıktısı. Dilim dışındaysa boş liste."""
    if dist is None or abs(ht[0] - ht[1]) != RULE_PARAMS["ht_deficit"]:
        return []
    trailing_home = ht[0] < ht[1]
    lam_t, lam_l = (dist["lam_h"], dist["lam_a"]) if trailing_home else (dist["lam_a"], dist["lam_h"])
    if lam_l <= 0 or lam_t / lam_l < RULE_PARAMS["min_lambda_ratio"]:
        return []
    ratio = round(lam_t / lam_l, 3)
    grid = dist["grid"]
    goal_market = "ev_05" if trailing_home else "dep_05"
    dc_selection = "1X" if trailing_home else "X2"
    picks = []
    goal_pct = _prob(grid, "h2", goal_market, "over")
    if goal_pct >= RULE_PARAMS["h2_goal_min_pct"]:
        picks.append({"period": "h2", "market": goal_market, "selection": "over", "pct": goal_pct,
                      "kind": "trailing_goal", "ratio": ratio, "tier": "high"})
    picks.append({"period": "ft", "market": "dc", "selection": dc_selection,
                  "pct": _prob(grid, "ft", "dc", dc_selection), "kind": "trailing_not_lose", "ratio": ratio,
                  "tier": "medium"})
    return picks


def ledger_rows(picks: list[dict], common: dict, *, lambdas: dict | None, late: bool = False) -> list[dict]:
    params = shadow_params_fingerprint()
    return [{
        **common, "source": "live_ht", "rule_version": LIVE_COMEBACK_SHADOW_VERSION,
        "period": p["period"], "market": p["market"], "selection": p["selection"], "archive": None,
        "prob_shown_bp": round(p["pct"] * 100), "sample_n": None, "confidence_tier": p["tier"],
        "details": {"shadow": True, "kind": p["kind"], "lambda_ratio": p["ratio"], "lambdas": lambdas,
                    "params": params, "late": late},
    } for p in picks]
