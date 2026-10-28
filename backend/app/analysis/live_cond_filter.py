"""Canlı "lig geçmişi yüksek, takımlar desteklemiyor" uyarısı — live-cond-filter-v1 (Sprint 94 Faz O, GÖLGE).

Fikir (denetim 28 Ekim): aynı lig + aynı İY skorlu geçmiş (COND) bir seçimi ≥%85 gösterirken takım gücü modeli
(live-poisson) aynı seçimi %85'in altında veriyor. 3 yıllık backtest'te bu dilim ~%88 gösterip %81,4 tuttu →
COND'un oranı bu maçlarda fazla iyimser. Gölge kayıt COND'un gösterdiği olasılıkla yazılır; karne "beklentinin
altında" çıkarsa uyarı işe yarıyor demektir (100 tekil karar sonrası). Ekranda yok.

Pazarlar ve olasılık ızgarası live-poisson ile aynı; COND tablosu C1 penceresiyle (son N yıl).
"""

from __future__ import annotations

import hashlib
import json

from app.analysis import live_poisson

LIVE_COND_FILTER_SHADOW_VERSION = "live-cond-filter-v1"
RULE_PARAMS = {
    "cond_min_pct": 85.0,
    "cond_min_n": 30,
    "model_below_pct": 85.0,
}


def shadow_params_fingerprint() -> str:
    from app.analysis.live_model import COND_WINDOW_YEARS

    payload = {"team_model": live_poisson.team_model_fingerprint(), **live_poisson.DECISION_PARAMS,
               **RULE_PARAMS, "cond_window_years": COND_WINDOW_YEARS}
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def warnings(prediction: dict | None, cond_of) -> list[dict]:
    """COND ≥%85 (≥30 maç) ama modelin aynı seçime verdiği olasılık <%85 olan seçimler."""
    if prediction is None:
        return []
    out = []
    excluded = {tuple(x) for x in live_poisson.DECISION_PARAMS["exclude"]}
    for cell in prediction["cells"]:
        for code, model_pct in cell["options"].items():
            if (cell["period"], cell["market"], code) in excluded or model_pct >= RULE_PARAMS["model_below_pct"]:
                continue
            cond = cond_of(cell["period"], cell["market"], code)
            if cond is None or cond["n"] < RULE_PARAMS["cond_min_n"] or cond["pct"] < RULE_PARAMS["cond_min_pct"]:
                continue
            out.append({"period": cell["period"], "market": cell["market"], "selection": code,
                        "cond_pct": cond["pct"], "cond_n": cond["n"], "model_pct": model_pct})
    return out


def ledger_rows(prediction: dict, picks: list[dict], common: dict, *, late: bool = False) -> list[dict]:
    """Gölge satırlar: gösterilen olasılık = COND oranı (sınanan iddia budur)."""
    params = shadow_params_fingerprint()
    return [{
        **common, "source": "live_ht", "rule_version": LIVE_COND_FILTER_SHADOW_VERSION,
        "period": p["period"], "market": p["market"], "selection": p["selection"], "archive": None,
        "prob_shown_bp": round(p["cond_pct"] * 100), "sample_n": p["cond_n"], "confidence_tier": "medium",
        "details": {"shadow": True, "cond_pct": p["cond_pct"], "cond_n": p["cond_n"], "model_pct": p["model_pct"],
                    "lambda_2h": prediction["lambda_2h"], "lambda_ft": prediction["lambda_ft"],
                    "params": params, "late": late},
    } for p in picks]
