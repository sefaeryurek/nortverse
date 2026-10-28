"""Canlı 2. yarı işaretleri (live-2h-v1.1) — GÖLGEDE: ekranda yok, sadece deftere yazılır.

Sprint 92 ajan ölçümü (6.071 ana lig maçı, 2023-07 → 2026-10, sızıntısız):
- Arşivler (A1/A2/A3/Genel) 2. yarı için kullanılabilir sinyal vermiyor: yüksek eşikte gösterilenin
  8–15 puan altında tutuyor. "İY 1-0, arşivde hep KG var" fikri %53,5 (aynı İY'de taban %51,4).
- İşe yarayan iki işaret, ikisi de takım gücü (Poisson) modelinden:
  (a) "Güvenli alt": ev/dep 1.5 alt (MS ve 2Y), olasılık = min(Poisson, COND) ≥ %85
      → 3.369 seçim %88,6 tuttu, gösterilen %86,5 (oranı düşük gelir).
  (b) "Gol": 2Y ev/dep gol atar, MS KG var (bir taraf henüz atmamışsa), MS ev/dep 0.5 üst;
      Poisson ≥ %70 → ~%77 tuttu, gösterilen ~%75 (COND bu pazarlarda %70'i hiç geçmiyor).
- Bahis oranı verisi yok → "değer" burada sadece "kalibre ve tabanın belirgin üstünde" demek; kârlılık iddiası yok.

Kurallar:
- İY skorunun zaten belirlediği pazarlar atlanır; aynı olayı anlatan iki pazar (ör. İY x-0'da
  MS dep 1.5 alt = 2Y dep 1.5 alt) tek karar sayılır (ilk sıradaki kalır).
- COND (aynı lig + aynı İY) ≥ %80 ise `trivial` işareti: zaten neredeyse kesin, değer katmıyor.
- 100 tekil karar dolmadan karne yok; ekrana alınması kullanıcı kararıdır.
"""

from __future__ import annotations

import hashlib
import json

from app.analysis.live_archive import _pair_hit, cond_probability, market_decided

# v1.1 (Sprint 94 C1+C2): parmak izine takım gücü modeli eklendi (Poisson ızgarasını o üretiyor) ve COND
# tablosu 10 yıllık pencereyle kurulur. Hâlâ gölge.
LIVE_2H_RULE_VERSION = "live-2h-v1.1"
LIVE_2H_RULE_VERSIONS = ("live-2h-v1", "live-2h-v1.1")  # değerlendirme geçmişi için
RULE_PARAMS = {
    "safe": {
        "prob": "min(poisson, cond)", "threshold_pct": 85.0,
        "markets": [["ft", "dep_15"], ["h2", "dep_15"], ["ft", "ev_15"], ["h2", "ev_15"]],
        "selection": "under",
    },
    "goal": {
        "prob": "poisson", "threshold_pct": 70.0,
        "markets": [["h2", "ev_05"], ["h2", "dep_05"], ["ft", "kg"], ["ft", "ev_05"], ["ft", "dep_05"]],
        "selection": {"kg": "yes", "default": "over"},
    },
    "trivial_cond_pct": 80.0,
    "dedupe_equivalent_events": True,
    "cond_window_years": 10,  # live_model.COND_WINDOW_YEARS ile aynı olmalı (testte sınanır)
}
_EXTRA = 9  # eşdeğer olay kontrolünde 2. yarı gol ızgarası 0..8


def rule_params_fingerprint() -> str:
    from app.analysis.live_poisson import team_model_fingerprint

    payload = {**RULE_PARAMS, "team_model": team_model_fingerprint()}
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def _selection(kind: str, market: str) -> str:
    sel = RULE_PARAMS[kind]["selection"]
    return sel if isinstance(sel, str) else sel.get(market, sel["default"])


def _event_signature(period: str, market: str, selection: str, ht: tuple[int, int]) -> tuple[bool, ...]:
    """Seçimin 2. yarı gol ızgarasındaki tuttu/tutmadı deseni → aynı desen = aynı olay."""
    return tuple(
        _pair_hit(period, market, selection, (ht[0], ht[1], ht[0] + i, ht[1] + j))
        for i in range(_EXTRA) for j in range(_EXTRA)
    )


def decide(grid: list[tuple[tuple[int, int, int, int], float]] | None, ht: tuple[int, int],
           cond_of) -> list[dict]:
    """Devre arası 2. yarı işaretleri. `grid`: live_poisson.final_grid()["grid"]; `cond_of(period, market,
    selection)` → cond_probability sonucu ya da None. Model yoksa karar yok."""
    if not grid:
        return []
    picks: list[dict] = []
    seen: set[tuple[bool, ...]] = set()
    for kind in ("safe", "goal"):
        spec = RULE_PARAMS[kind]
        for period, market in spec["markets"]:
            if market_decided(period, market, ht):
                continue
            selection = _selection(kind, market)
            signature = _event_signature(period, market, selection, ht)
            if not any(signature) or all(signature):
                continue  # kesinleşmiş (ör. 2Y'de imkânsız) — İY belirlemiş sayılır
            poisson = 100 * sum(p for pair, p in grid if _pair_hit(period, market, selection, pair))
            cond = cond_of(period, market, selection)
            if kind == "safe":
                if cond is None:
                    continue  # COND kapısı olmadan güvenli işaret yok
                prob = min(poisson, cond["pct"])
            else:
                prob = poisson
            if prob < spec["threshold_pct"]:
                continue
            if RULE_PARAMS["dedupe_equivalent_events"] and signature in seen:
                continue
            seen.add(signature)
            picks.append({
                "kind": kind, "period": period, "market": market, "selection": selection,
                "pct": round(prob, 1), "poisson_pct": round(poisson, 1),
                "cond_pct": cond["pct"] if cond else None, "cond_n": cond["n"] if cond else None,
                "cond_level": cond["level"] if cond else None,
                "trivial": bool(cond and cond["pct"] >= RULE_PARAMS["trivial_cond_pct"]),
            })
    return picks


def ledger_rows(picks: list[dict], common: dict, *, lambdas: dict | None = None,
                late: bool = False) -> list[dict]:
    """Gölge kayıtlar: ekranda ve değerlendirme özetinde görünmez, sadece ölçülür."""
    return [{
        **common, "source": "live_ht", "rule_version": LIVE_2H_RULE_VERSION,
        "period": p["period"], "market": p["market"], "selection": p["selection"], "archive": None,
        "prob_shown_bp": round(p["pct"] * 100), "sample_n": p["cond_n"],
        "confidence_tier": "high" if p["kind"] == "safe" else "medium",
        "details": {"shadow": True, "kind": p["kind"], "poisson_pct": p["poisson_pct"],
                    "cond_pct": p["cond_pct"], "cond_n": p["cond_n"], "cond_level": p["cond_level"],
                    "trivial": p["trivial"], "lambdas": lambdas, "params": rule_params_fingerprint(),
                    "late": late},
    } for p in picks]


def cond_lookup(table, league: str, ht: tuple[int, int]):
    return lambda period, market, sel: cond_probability(table, league, ht, period, market, sel)
