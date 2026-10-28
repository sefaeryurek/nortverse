"""live-comeback-v1 (Sprint 94 Faz O3, gölge): İY'de 1 farkla geride olan güçlü takım."""

from app.analysis import live_comeback as lc


def _dist(lam_h, lam_a, ht, cells):
    """Basit ızgara: (iy_ev, iy_dep, ms_ev, ms_dep) → olasılık."""
    return {"lam_h": lam_h, "lam_a": lam_a, "r_h": 0, "r_a": 0,
            "grid": [((ht[0], ht[1], ht[0] + h, ht[1] + a), p) for (h, a), p in cells.items()]}


def test_strong_trailing_home_gets_goal_and_not_lose():
    ht = (0, 1)
    dist = _dist(2.4, 0.9, ht, {(0, 0): 0.2, (1, 0): 0.3, (2, 0): 0.4, (1, 1): 0.1})
    picks = {p["kind"]: p for p in lc.decide(dist, ht)}
    assert picks["trailing_goal"]["market"] == "ev_05" and picks["trailing_goal"]["pct"] == 80.0
    assert picks["trailing_not_lose"]["selection"] == "1X" and picks["trailing_not_lose"]["pct"] == 70.0  # 1-1 + 2-1
    assert picks["trailing_not_lose"]["tier"] == "medium" and picks["trailing_goal"]["ratio"] == round(2.4 / 0.9, 3)


def test_goal_pick_needs_65_and_slice_needs_ratio_and_one_goal_deficit():
    ht = (1, 0)
    weak_goal = _dist(0.8, 2.0, ht, {(0, 0): 0.4, (0, 1): 0.6})  # deplasman geride, 2Y gol %60
    kinds = [p["kind"] for p in lc.decide(weak_goal, ht)]
    assert kinds == ["trailing_not_lose"]
    assert lc.decide(_dist(1.5, 1.0, ht, {(0, 1): 1.0}), ht) == []     # oran 1,5 < 2,2
    assert lc.decide(_dist(0.5, 2.0, (2, 0), {(0, 1): 1.0}), (2, 0)) == []  # 2 fark
    assert lc.decide(None, ht) == []


def test_ledger_rows_are_shadow():
    picks = [{"period": "ft", "market": "dc", "selection": "X2", "pct": 70.0, "kind": "trailing_not_lose",
              "ratio": 2.5, "tier": "medium"}]
    (row,) = lc.ledger_rows(picks, {"match_id": "1"}, lambdas=None)
    assert row["rule_version"] == "live-comeback-v1" and row["confidence_tier"] == "medium"
    assert row["details"]["shadow"] is True and row["prob_shown_bp"] == 7000
