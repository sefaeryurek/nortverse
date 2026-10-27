"""İY değer (value) kuralı — ht-value-v1 (Sprint 93, kullanıcı isteği: "amaç value değerler bulmak").

Model olasılığı (`prematch_ht`, takım gücü × lig İY gol payı) bahis oranıyla (Bet365, `scraper.odds`) kıyaslanır:
beklenen getiri EV = olasılık × oran − 1 (1 birim bahiste ortalama kâr). Sadece sitenin gerçekten açtığı pazarlar:
- İY 1X2 (ondalık oran)
- İY Asya Ü/A, sitenin verdiği ana çizgide (0.75, 1.0, 1.25 ...): tam sayı çizgide iade, çeyrek çizgide yarım
  kazanç/kayıp kesin hesaplanır.
İY çifte şans ve 1.5 alt gösterilmez (oranları ya yok ya ~1.10). Eşikler geçmiş kapanış oranlarıyla ölçülür
(`backtest-ht-value`); ölçüm sonucu aşağıda RULE_PARAMS yanında.
"""

from __future__ import annotations

import hashlib
import json

from app.analysis.prematch_ht import _pmf

HT_VALUE_RULE_VERSION = "ht-value-v1"
RULE_PARAMS = {
    "result_selections": ["1", "X", "2"],
    "total_sides": ["over", "under"],
    "min_ev": 0.05,
    "min_prob": 0.30,
    "max_odds": 6.0,
}


def rule_params_fingerprint() -> str:
    return hashlib.sha1(json.dumps(RULE_PARAMS, sort_keys=True).encode()).hexdigest()[:12]


def ht_grid(lam_h: float, lam_a: float) -> list[tuple[int, int, float]]:
    ph, pa = _pmf(lam_h), _pmf(lam_a)
    return [(i, j, ph[i] * pa[j]) for i in range(len(ph)) for j in range(len(pa))]


def _half_lines(line: float) -> list[float]:
    """Çeyrek çizgi iki yarım bahse bölünür (1.25 → 1.0 + 1.5); diğerleri tek."""
    frac = round(line * 4) % 4
    return [line - 0.25, line + 0.25] if frac in (1, 3) else [line]


def total_return(total: int, line: float, side: str, odds: float) -> float:
    """Asya Ü/A, 1 birim bahsin net kârı (kayıp −1, iade 0, yarım sonuçlar dahil)."""
    parts = _half_lines(line)
    out = 0.0
    for part in parts:
        if total == part:
            r = 0.0
        else:
            won = total > part if side == "over" else total < part
            r = (odds - 1) if won else -1.0
        out += r / len(parts)
    return out


def candidates(lam_h: float, lam_a: float, odds: dict) -> list[dict]:
    """Oranı olan tüm İY seçimlerinin model olasılığı ve beklenen getirisi (karar süzgeci `decide`'da)."""
    grid = ht_grid(lam_h, lam_a)
    out: list[dict] = []
    op = odds.get("op")
    if op:
        probs = {"1": sum(p for i, j, p in grid if i > j), "X": sum(p for i, j, p in grid if i == j),
                 "2": sum(p for i, j, p in grid if i < j)}
        for sel in RULE_PARAMS["result_selections"]:
            price = op.get(sel)
            if price:
                out.append({"market": "result", "selection": sel, "line": None, "odds": price,
                            "prob": probs[sel], "ev": probs[sel] * price - 1})
    ou = odds.get("ou")
    if ou:
        totals: dict[int, float] = {}
        for i, j, p in grid:
            totals[i + j] = totals.get(i + j, 0.0) + p
        for side in RULE_PARAMS["total_sides"]:
            price = ou.get(side)
            if not price:
                continue
            ev = sum(p * total_return(t, ou["line"], side, price) for t, p in totals.items())
            win = sum(p for t, p in totals.items() if total_return(t, ou["line"], side, price) > 0)
            out.append({"market": "ou", "selection": side, "line": ou["line"], "odds": price,
                        "prob": win, "ev": ev})
    return out


def decide(cands: list[dict], params: dict | None = None) -> list[dict]:
    """Değer eşiğini geçen seçimler — pazar başına en yüksek EV'li tek seçim, EV'ye göre azalan."""
    p = params or RULE_PARAMS
    best: dict[str, dict] = {}
    for c in cands:
        if c["ev"] < p["min_ev"] or c["prob"] < p["min_prob"] or c["odds"] > p["max_odds"]:
            continue
        if c["market"] not in best or c["ev"] > best[c["market"]]["ev"]:
            best[c["market"]] = c
    return sorted(best.values(), key=lambda c: -c["ev"])


def settle(pick: dict, ht: tuple[int, int]) -> float:
    """Gerçek İY skoruyla 1 birim bahsin net kârı."""
    h, a = ht
    if pick["market"] == "result":
        actual = "1" if h > a else "2" if h < a else "X"
        return pick["odds"] - 1 if actual == pick["selection"] else -1.0
    return total_return(h + a, pick["line"], pick["selection"], pick["odds"])
