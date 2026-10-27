"""Maç öncesi İY kuralı (ht-display-v1)."""

from app.analysis import prematch_ht as ht


def test_rule_params_fingerprint_is_pinned():
    # Kural değişirse bu test kırılır: sabiti güncelle VE HT_RULE_VERSION'ı artır.
    assert (ht.HT_RULE_VERSION, ht.rule_params_fingerprint()) == ("ht-display-v1", "19735060419a")


def test_probabilities_are_consistent():
    p = ht.ht_probabilities(1.8, 0.9, (0.45, 0.44))
    assert abs(sum(p["result"].values()) - 100) < 0.5
    assert abs(p["dc"]["1X"] - (p["result"]["1"] + p["result"]["X"])) < 0.2
    assert abs(p["ou_05"]["over"] + p["ou_05"]["under"] - 100) < 0.2
    assert p["lambda"] == {"home": round(1.8 * 0.45, 3), "away": round(0.9 * 0.44, 3)}
    assert len(p["top_scores"]) == 3 and p["top_scores"][0]["score"] == "0-0"


def test_strong_home_favourite_gets_picks_but_never_draw():
    p = ht.ht_probabilities(2.6, 0.5, (0.46, 0.44))
    picks = ht.decide(p, {"1": 0.33, "X": 0.42, "2": 0.25, "goal": 0.74, "under15": 0.66, "home_scores": 0.52})
    by_market = {x["market"]: x for x in picks}
    assert by_market["dc"]["selection"] == "1X" and by_market["dc"]["pct"] >= 80
    assert by_market["result"]["selection"] == "1"
    assert all(x["selection"] != "X" for x in picks)
    assert by_market["dc"]["base_pct"] == 75.0


def test_even_match_has_no_result_pick():
    p = ht.ht_probabilities(1.3, 1.2, (0.45, 0.45))
    assert not any(x["market"] in ("result", "dc") for x in ht.decide(p, {}))


def test_ledger_rows_mark_informational_markets():
    view = {"probs": ht.ht_probabilities(2.6, 0.5, (0.46, 0.44)), "picks": []}
    view["picks"] = ht.decide(view["probs"], None)
    rows = ht.ledger_rows(view, {"match_id": "1"})
    assert {r["market"] for r in rows if r["informational"]} == {"kg", "dep_05"}
    assert all(r["period"] == "ht" and r["rule_version"] == "ht-display-v1" for r in rows)
