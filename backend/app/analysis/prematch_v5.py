"""Maç öncesi strateji v5 (ft-display-v5): Dixon-Coles takım gücü modeli.

Sprint 91 ajan ölçümü: arşivler maç öncesinde lig ortalamasını geçemiyordu (A1 %41,4 < lig %43,5);
takım gücüne dayalı Dixon-Coles modeli %51,7 tuttu, lig ortalamasından ≥10 puan ayrıştığı seçimlerde ~%61.

Kural:
- Takım gücü `live_poisson` ile ortak (lig başına zaman ağırlıklı Poisson + Dixon-Coles rho).
- MS 1X2 olasılıkları skor ızgarasından; seçim 1 veya 2 (X yayınlanmaz), lig ortalamasına göre avantajı
  en büyük olan. Avantaj < 10 puan → yayın yok.
- Kademe: v4 (arşiv havuzu) aynı seçimi yayınladıysa "high", yoksa "medium".
- Ü/A 2.5 ve KG deftere sadece bilgi amaçlı (`informational`).

v4 gölgede kaydedilmeye devam eder; karşılaştırma Değerlendirme → Maç Öncesi'nde.
"""

from __future__ import annotations

import hashlib
import json
import math

from app.analysis.live_poisson import PoissonModel, dc_tau
from app.analysis.live_poisson import rule_params_fingerprint as team_model_fingerprint

V5_RULE_VERSION = "ft-display-v5"
RULE_PARAMS = {
    "team_model": "live-poisson team strength + dixon-coles rho",
    "min_edge": 0.10, "exclude": ["X"], "max_goals": 10,
    "tier_high": "v4 agrees", "informational": ["ou_25", "kg"],
}
_RESULT_FIELDS = {"1": "result_1_pct", "X": "result_x_pct", "2": "result_2_pct"}


def rule_params_fingerprint() -> str:
    payload = {**RULE_PARAMS, "team_model_params": team_model_fingerprint()}
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def _pmf(lam: float, n: int) -> list[float]:
    return [math.exp(-lam) * lam ** k / math.factorial(k) for k in range(n + 1)]


def match_probabilities(model: PoissonModel, league: str, home: str, away: str) -> dict | None:
    """MS 1/X/2, Üst 2.5 ve KG Var olasılıkları (Dixon-Coles düzeltmeli skor ızgarası)."""
    lm = model.leagues.get(league)
    if lm is None:
        return None
    lam_h, lam_a = lm.expected_goals(home, away)
    n = RULE_PARAMS["max_goals"]
    ph, pa = _pmf(lam_h, n), _pmf(lam_a, n)
    probs = {"1": 0.0, "X": 0.0, "2": 0.0}
    over25 = btts = total = 0.0
    for x in range(n + 1):
        for y in range(n + 1):
            p = ph[x] * pa[y] * dc_tau(x, y, lam_h, lam_a, lm.rho)
            total += p
            probs["1" if x > y else "X" if x == y else "2"] += p
            over25 += p if x + y >= 3 else 0.0
            btts += p if x > 0 and y > 0 else 0.0
    return {
        "result": {k: v / total for k, v in probs.items()},
        "over25": over25 / total, "btts": btts / total,
        "lambda": {"home": round(lam_h, 3), "away": round(lam_a, 3)}, "rho": round(lm.rho, 4),
        "train_n": lm.n,
    }


def decide(probabilities: dict | None, prior: dict[str, float], v4_selection: str | None) -> dict:
    """Yayın kararı; yayınlanmayacaksa `abstain_reason` dolu."""
    if probabilities is None:
        return {"abstain_reason": "no_team_model"}
    result = probabilities["result"]
    candidates = [o for o in ("1", "X", "2") if o not in RULE_PARAMS["exclude"]]
    pick = max(candidates, key=lambda o: result[o] - prior[o])
    edge = result[pick] - prior[pick]
    decision = {"selection": pick, "prob": result[pick], "edge": edge, "probs": result, "prior": prior,
                "v4_agrees": v4_selection == pick, "tier": "high" if v4_selection == pick else "medium"}
    if edge < RULE_PARAMS["min_edge"]:
        decision["abstain_reason"] = "edge_below_minimum"
    return decision


def build_v5_recommendations(probabilities: dict | None, prior: dict[str, float], v4_selection: str | None,
                             patterns: dict | None) -> list[dict]:
    """Ekrandaki Top Picks satırı (v4 ile aynı biçim; arşiv yüzdeleri bilgi olarak)."""
    decision = decide(probabilities, prior, v4_selection)
    if decision.get("abstain_reason"):
        return []
    pick = decision["selection"]
    row = {
        "recommendation_id": f"{V5_RULE_VERSION}:result:{pick}",
        "archive": "model",
        "market": "result",
        "selection": pick,
        "frequency_pct": round(decision["prob"] * 100, 2),
        "match_count": probabilities["train_n"],
        "calibrated_pct": round(decision["prob"] * 100, 1),
        "margin": round(decision["edge"] * 100, 1),
        "is_confident": decision["tier"] == "high",
        "confidence_tier": decision["tier"],
        "prior_pct": round(prior[pick] * 100, 1),
        "agreement": 1 if decision["v4_agrees"] else 0,
    }
    for name, family in (("archive_1", "b"), ("archive_2", "c"), ("archive_3", "d")):
        blob = (patterns or {}).get(f"pattern_ft_{family}")
        ok = isinstance(blob, dict) and blob.get("match_count")
        row[f"{name}_frequency_pct"] = round(blob.get(_RESULT_FIELDS[pick], 0.0), 2) if ok else None
        row[f"{name}_match_count"] = blob["match_count"] if ok else None
    return [row]


def ledger_rows_v5(probabilities: dict | None, prior: dict[str, float], goal_prior: dict[str, float],
                   v4_selection: str | None, common: dict) -> list[dict]:
    rows: list[dict] = []
    decision = decide(probabilities, prior, v4_selection)
    if not decision.get("abstain_reason"):
        pick = decision["selection"]
        prior_pick = max(prior, key=prior.get)
        rows.append({
            **common, "source": "top_pick", "rule_version": V5_RULE_VERSION, "period": "ft",
            "market": "result", "selection": pick, "prob_shown_bp": round(decision["prob"] * 10000),
            "baseline_selection": prior_pick, "baseline_prob_bp": round(prior[prior_pick] * 10000),
            "confidence_tier": decision["tier"], "sample_n": probabilities["train_n"],
            "agreement": 1 if decision["v4_agrees"] else 0,
            "details": {"probs": decision["probs"], "prior": prior, "edge": decision["edge"],
                        "lambda": probabilities["lambda"], "rho": probabilities["rho"],
                        "v4_selection": v4_selection, "params": rule_params_fingerprint()},
        })
    if probabilities is not None:
        for market, key, yes, no, prior_key in (("ou_25", "over25", "over", "under", "over25"),
                                                ("kg", "btts", "yes", "no", "btts")):
            p_yes = probabilities[key]
            pick, prob = (yes, p_yes) if p_yes >= 0.5 else (no, 1 - p_yes)
            base_yes = goal_prior[prior_key]
            rows.append({
                **common, "source": "top_pick", "rule_version": V5_RULE_VERSION, "period": "ft",
                "market": market, "selection": pick, "prob_shown_bp": round(prob * 10000),
                "baseline_selection": yes if base_yes >= 0.5 else no,
                "baseline_prob_bp": round(max(base_yes, 1 - base_yes) * 10000),
                "sample_n": probabilities["train_n"], "informational": True,
                "details": {"p_yes": p_yes, "prior_yes": base_yes},
            })
    return rows


async def capture_recommendations(
    session, *, match_id: str, analyzed_at, captured_at, kickoff_time, league_name: str | None,
    league_code: str | None, patterns: dict | None, pattern_hash: str | None = None,
) -> tuple[list[dict] | None, bool]:
    """Maç öncesi kararları bir kez dondurur: v4 (gölge) + v5 (ekranda). Ekranda gösterilecek v5 seçimini döner.

    Uygunluk ve "maç başlamış mı" koruması v4 ile ortak: v4 None dönerse (uygun değil) v5 de yazılmaz.
    v4 daha önce dondurulmuş olsa da v5 ayrıca denenir (sürüm geçişinde aynı gün analiz edilen maçlar).
    """
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert

    from app.analysis.ledger import record_predictions
    from app.analysis.league_filter import canonical_league_name
    from app.analysis.live_model import get_cond_table
    from app.analysis.live_poisson import get_poisson_model
    from app.analysis.persist import hash_string, pattern_hashes
    from app.analysis.prematch_v4 import capture_v4_recommendations, decide_result
    from app.db.models import AnalysisSnapshot, Match

    v4_picks, _ = await capture_v4_recommendations(
        session, match_id=match_id, analyzed_at=analyzed_at, captured_at=captured_at,
        kickoff_time=kickoff_time, league_name=league_name, league_code=league_code, patterns=patterns,
        pattern_hash=pattern_hash,
    )
    if v4_picks is None:
        return None, False
    existing = await session.get(AnalysisSnapshot, (match_id, V5_RULE_VERSION))
    if existing is not None:
        return (existing.picks if isinstance(existing.picks, list) else []), False

    league = canonical_league_name(league_name or league_code or "")
    teams = (await session.execute(
        select(Match.home_team, Match.away_team, Match.league_name).where(Match.match_id == match_id)
    )).first()
    if teams is None:
        return [], False
    table = await get_cond_table()
    prior = table.league_prior(league)
    v4 = decide_result(patterns or {}, prior)
    v4_selection = v4["selection"] if v4 and not v4.get("abstain_reason") else None
    probabilities = match_probabilities(await get_poisson_model(), teams.league_name or league,
                                        teams.home_team, teams.away_team)
    phash = pattern_hash or hash_string(pattern_hashes())
    picks = [{**pick, "pattern_hash": phash}
             for pick in build_v5_recommendations(probabilities, prior, v4_selection, patterns)]
    written = await session.execute(
        insert(AnalysisSnapshot).values(
            match_id=match_id, rule_version=V5_RULE_VERSION, captured_at=captured_at,
            analyzed_at=analyzed_at, kickoff_time=kickoff_time, league_name=league or "unknown", picks=picks,
        ).on_conflict_do_nothing(index_elements=["match_id", "rule_version"])
    )
    if written.rowcount != 1:
        snapshot = await session.get(AnalysisSnapshot, (match_id, V5_RULE_VERSION))
        return (snapshot.picks if snapshot and isinstance(snapshot.picks, list) else []), False
    common = {"match_id": match_id, "league_name": league, "kickoff_time": kickoff_time,
              "as_of": captured_at, "pattern_hash": phash}
    await record_predictions(session, ledger_rows_v5(
        probabilities, prior, table.league_goal_prior(league), v4_selection, common))
    return picks, True
