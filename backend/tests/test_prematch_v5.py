"""Maç öncesi v5 (Dixon-Coles takım gücü): olasılıklar, yayın kuralı, kademe, defter satırları."""

import pytest

from app.analysis import prematch_v5 as v5
from app.analysis.live_poisson import LeagueModel, PoissonModel, dc_tau

PRIOR = {"1": 0.45, "X": 0.26, "2": 0.29}
GOAL_PRIOR = {"over25": 0.55, "btts": 0.52}


def _model(rho=-0.05):
    lm = LeagueModel(mu=0.25, home_adv=0.2, attack={"Strong": 0.5, "Weak": -0.4},
                     defense={"Strong": 0.3, "Weak": -0.3}, n=900, rho=rho)
    return PoissonModel(as_of=None, leagues={"L": lm})


def test_rule_params_fingerprint_is_pinned():
    # Kural/takım modeli parametresi değişirse V5_RULE_VERSION artırılmalı.
    assert v5.V5_RULE_VERSION == "ft-display-v5"
    assert v5.rule_params_fingerprint() == "60715673e89e"


def test_probabilities_sum_to_one_and_favour_strong_home():
    probs = v5.match_probabilities(_model(), "L", "Strong", "Weak")
    assert sum(probs["result"].values()) == pytest.approx(1.0)
    assert probs["result"]["1"] > 0.6 > probs["result"]["2"]
    assert 0 < probs["over25"] < 1 and 0 < probs["btts"] < 1
    assert v5.match_probabilities(_model(), "Unknown", "Strong", "Weak") is None


def test_negative_rho_raises_draw_probability():
    assert dc_tau(0, 0, 1.2, 1.0, -0.1) > 1 and dc_tau(1, 0, 1.2, 1.0, -0.1) < 1
    with_rho = v5.match_probabilities(_model(rho=-0.1), "L", "Weak", "Strong")["result"]["X"]
    without = v5.match_probabilities(_model(rho=0.0), "L", "Weak", "Strong")["result"]["X"]
    assert with_rho > without


def test_decide_publishes_only_with_edge_and_never_draw():
    probs = {"result": {"1": 0.62, "X": 0.22, "2": 0.16}, "train_n": 900}
    decision = v5.decide(probs, PRIOR, "1")
    assert decision["selection"] == "1" and decision["tier"] == "high" and "abstain_reason" not in decision
    assert v5.decide(probs, PRIOR, "2")["tier"] == "medium"
    small = {"result": {"1": 0.50, "X": 0.27, "2": 0.23}, "train_n": 900}   # avantaj 5 puan
    assert v5.decide(small, PRIOR, None)["abstain_reason"] == "edge_below_minimum"
    draw_heavy = {"result": {"1": 0.30, "X": 0.45, "2": 0.25}, "train_n": 900}
    assert v5.decide(draw_heavy, PRIOR, None)["selection"] != "X"
    assert v5.decide(None, PRIOR, None)["abstain_reason"] == "no_team_model"


def test_recommendation_and_ledger_rows():
    probs = v5.match_probabilities(_model(), "L", "Strong", "Weak")
    patterns = {"pattern_ft_b": {"match_count": 40, "result_1_pct": 61.0}}
    picks = v5.build_v5_recommendations(probs, PRIOR, "1", patterns)
    assert len(picks) == 1 and picks[0]["archive"] == "model" and picks[0]["agreement"] == 1
    assert picks[0]["archive_1_frequency_pct"] == 61.0 and picks[0]["archive_2_match_count"] is None
    rows = v5.ledger_rows_v5(probs, PRIOR, GOAL_PRIOR, "1", {"match_id": "1"})
    main = [r for r in rows if not r.get("informational")]
    assert [r["market"] for r in main] == ["result"] and main[0]["rule_version"] == "ft-display-v5"
    assert {r["market"] for r in rows if r.get("informational")} == {"ou_25", "kg"}


def test_v51_tier_follows_edge_not_v4():
    """Sprint 94 O5: kademe avantaja bağlı (≥20 high, ≥15 medium, ≥10 low); seçim v5 ile aynı, gölge."""
    from app.analysis.prematch_v5 import edge_tier, ledger_rows_v51

    assert [edge_tier(e) for e in (0.25, 0.20, 0.17, 0.12)] == ["high", "high", "medium", "low"]
    prior = {"1": 0.45, "X": 0.27, "2": 0.28}
    probs = {"result": {"1": 0.62, "X": 0.22, "2": 0.16}, "lambda": {"home": 1.8, "away": 0.9}, "rho": -0.05,
             "train_n": 900, "over25": 0.5, "btts": 0.5}
    (row,) = ledger_rows_v51(probs, prior, {"match_id": "1"}, model_only=True)
    assert row["rule_version"] == "ft-display-v5.1" and row["selection"] == "1"
    assert row["confidence_tier"] == "medium"  # avantaj 17 puan
    assert row["details"]["shadow"] is True and row["details"]["model_only"] is True
    weak = {**probs, "result": {"1": 0.50, "X": 0.27, "2": 0.23}}
    assert ledger_rows_v51(weak, prior, {"match_id": "1"}) == []  # avantaj <10 → yayın yok
