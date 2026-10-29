"""Maç öncesi İLK YARI (İY) tahminleri — ht-display-v1.1 (Sprint 93, ekranda "Deneme" etiketiyle).

Model: maç öncesi takım gücü (`live_poisson`, v5 ile aynı) → İY λ = maç λ × ligin İY gol payı (ev/dep ayrı,
eğitim penceresinden) → bağımsız Poisson İY skor ızgarası. Arşivler (A1/A2/A3) İY'de lig ortalamasından bile
kötü çıktı → karar kaynağı değil.

Sızıntısız tekrar oynatma (6.126 ana lig maçı, 2023-07 → 2026-10, haftalık model):
- İY çifte şans ≥%85: 770 seçim %88,7 (gösterilen %87,7, lig ort. %73,5); ≥%80: 2.275 seçim %84,9
- İY 1 veya 2 ≥%50 (X asla): 648 seçim %58,5 (gösterilen %56,0, lig ort. %33,7)
- İY gol var (0.5 üst) ≥%80: 396 seçim %83,3 · İY 1.5 alt ≥%70: 1.180 seçim %72,3
- İY ev sahibi gol atar ≥%65: 502 seçim %73,7
Gösterilmeyenler: İY X ("hep X" tuzağı, tabanı geçmiyor), İY KG (beceri yok) → sadece bilgi.
"""

from __future__ import annotations

import hashlib
import json

from app.analysis.poisson_utils import pmf

# v1.1 (Sprint 94 C2): λ'ları üreten takım gücü modeli parmak izine girdi (model değişse sürüm atlamıyordu).
HT_RULE_VERSION = "ht-display-v1.1"
HT_RULE_VERSIONS = ("ht-display-v1", "ht-display-v1.1")  # o gün dondurulmuş eski kayıtlar okunabilsin
RULE_PARAMS = {
    "share": "league_ht_goal_share_home_away",
    "markets": {
        "dc": {"selections": ["1X", "X2"], "min_pct": 80.0, "high_pct": 85.0},
        "result": {"selections": ["1", "2"], "min_pct": 50.0, "high_pct": 55.0},
        "ou_05": {"selections": ["over"], "min_pct": 80.0, "high_pct": 85.0},
        "ou_15": {"selections": ["under"], "min_pct": 70.0, "high_pct": 80.0},
        "ev_05": {"selections": ["over"], "min_pct": 65.0, "high_pct": 75.0},
    },
    "informational": ["kg", "dep_05"],
    "max_goals": 8,
}
_N = RULE_PARAMS["max_goals"]


def rule_params_fingerprint() -> str:
    from app.analysis.live_poisson import team_model_fingerprint

    payload = {**RULE_PARAMS, "team_model": team_model_fingerprint()}
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def _pmf(lam: float) -> list[float]:
    return pmf(lam, _N, tail=True)


def ht_probabilities(lam_ft_home: float, lam_ft_away: float, share: tuple[float, float]) -> dict:
    """İY λ'ları ve İY pazarlarının olasılıkları (yüzde)."""
    lh, la = lam_ft_home * share[0], lam_ft_away * share[1]
    ph, pa = _pmf(lh), _pmf(la)
    grid = [(i, j, ph[i] * pa[j]) for i in range(len(ph)) for j in range(len(pa))]

    def pct(cond) -> float:
        return round(100 * sum(p for i, j, p in grid if cond(i, j)), 1)

    p1, px, p2 = pct(lambda i, j: i > j), pct(lambda i, j: i == j), pct(lambda i, j: i < j)
    top = sorted(grid, key=lambda c: -c[2])[:3]
    return {
        "lambda": {"home": round(lh, 3), "away": round(la, 3)},
        "result": {"1": p1, "X": px, "2": p2},
        "dc": {"1X": round(p1 + px, 1), "X2": round(px + p2, 1), "12": round(p1 + p2, 1)},
        "ou_05": {"over": pct(lambda i, j: i + j > 0), "under": pct(lambda i, j: i + j == 0)},
        "ou_15": {"over": pct(lambda i, j: i + j > 1), "under": pct(lambda i, j: i + j <= 1)},
        "ev_05": {"over": pct(lambda i, j: i > 0), "under": pct(lambda i, j: i == 0)},
        "dep_05": {"over": pct(lambda i, j: j > 0), "under": pct(lambda i, j: j == 0)},
        "kg": {"yes": pct(lambda i, j: i > 0 and j > 0), "no": pct(lambda i, j: i == 0 or j == 0)},
        "top_scores": [{"score": f"{i}-{j}", "pct": round(100 * p, 1)} for i, j, p in top],
    }


_BASE_KEYS = {  # lig İY ortalaması (LeagueModel.ht_base) → pazar seçimi
    ("result", "1"): lambda b: b.get("1"), ("result", "2"): lambda b: b.get("2"),
    ("dc", "1X"): lambda b: (b.get("1", 0) + b.get("X", 0)), ("dc", "X2"): lambda b: (b.get("X", 0) + b.get("2", 0)),
    ("ou_05", "over"): lambda b: b.get("goal"), ("ou_15", "under"): lambda b: b.get("under15"),
    ("ev_05", "over"): lambda b: b.get("home_scores"),
}


def decide(probs: dict | None, ht_base: dict[str, float] | None) -> list[dict]:
    """Pazar başına en fazla bir İY kararı (eşik üstü en yüksek seçim)."""
    if probs is None:
        return []
    picks = []
    for market, spec in RULE_PARAMS["markets"].items():
        best = max(spec["selections"], key=lambda s: probs[market][s])
        pct = probs[market][best]
        if pct < spec["min_pct"]:
            continue
        base_fn = _BASE_KEYS.get((market, best))
        base = base_fn(ht_base) if base_fn and ht_base else None
        picks.append({
            "period": "ht", "market": market, "selection": best, "pct": pct,
            "tier": "high" if pct >= spec["high_pct"] else "medium",
            "base_pct": round(100 * base, 1) if base is not None else None,
        })
    return sorted(picks, key=lambda p: -p["pct"])


def match_ht(model, league: str, home: str, away: str) -> dict | None:
    """Tek maç: İY olasılıkları + kararlar. Ligde model yoksa None."""
    lm = model.leagues.get(league) if model is not None else None
    if lm is None:
        return None
    lam_h, lam_a = lm.expected_goals(home, away)
    probs = ht_probabilities(lam_h, lam_a, lm.ht_share)
    return {"probs": probs, "picks": decide(probs, lm.ht_base),
            "league_base": {k: round(100 * v, 1) for k, v in lm.ht_base.items()}}


def ledger_rows(view: dict, common: dict) -> list[dict]:
    """Kararlar (Top Picks gibi) + bilgi amaçlı pazarlar deftere."""
    rows = [{
        **common, "source": "top_pick", "rule_version": HT_RULE_VERSION, "period": "ht",
        "market": p["market"], "selection": p["selection"], "archive": None,
        "prob_shown_bp": round(p["pct"] * 100),
        "baseline_prob_bp": round(p["base_pct"] * 100) if p["base_pct"] is not None else None,
        "confidence_tier": p["tier"], "informational": False,
        "details": {"lambda": view["probs"]["lambda"], "params": rule_params_fingerprint()},
    } for p in view["picks"]]
    for market in RULE_PARAMS["informational"]:
        options = view["probs"][market]
        best = max(options, key=options.get)
        rows.append({
            **common, "source": "top_pick", "rule_version": HT_RULE_VERSION, "period": "ht",
            "market": market, "selection": best, "archive": None,
            "prob_shown_bp": round(options[best] * 100), "confidence_tier": "low", "informational": True,
            "details": {"lambda": view["probs"]["lambda"], "params": rule_params_fingerprint()},
        })
    return rows


async def capture_ht(session, *, match_id: str, analyzed_at, captured_at, kickoff_time, league: str,
                     home: str, away: str, model, pattern_hash: str | None) -> list[dict] | None:
    """İY kararını bir kez dondurur (snapshot + defter, aynı transaction). Uygunluk çağıranda (v4/v5 ile aynı)."""
    from sqlalchemy.dialects.postgresql import insert

    from app.analysis.ledger import record_predictions
    from app.db.models import AnalysisSnapshot

    existing = await session.get(AnalysisSnapshot, (match_id, HT_RULE_VERSION))
    if existing is not None:
        return existing.picks if isinstance(existing.picks, list) else []
    view = match_ht(model, league, home, away)
    if view is None:
        return None
    picks = [{**p, "recommendation_id": f"{HT_RULE_VERSION}:{p['market']}:{p['selection']}",
              "probs": view["probs"], "pattern_hash": pattern_hash} for p in view["picks"]]
    written = await session.execute(
        insert(AnalysisSnapshot).values(
            match_id=match_id, rule_version=HT_RULE_VERSION, captured_at=captured_at,
            analyzed_at=analyzed_at, kickoff_time=kickoff_time, league_name=league or "unknown",
            picks=picks or [{"recommendation_id": f"{HT_RULE_VERSION}:none", "probs": view["probs"],
                             "abstain": True}],
        ).on_conflict_do_nothing(index_elements=["match_id", "rule_version"])
    )
    if written.rowcount == 1:
        await record_predictions(session, ledger_rows(view, {
            "match_id": match_id, "league_name": league, "kickoff_time": kickoff_time,
            "as_of": captured_at, "pattern_hash": pattern_hash,
        }))
    return picks
