"""Maç öncesi strateji v4: yayın kapısı, ekran formatı, defter satırları, sürüm disiplini."""

from datetime import datetime, timezone

from app.analysis import prematch_v4
from app.analysis.prematch_v4 import (
    V4_RULE_VERSION, build_v4_recommendations, decide_result, ledger_rows_v4, rule_params_fingerprint,
)

PRIOR = {"1": 0.45, "X": 0.25, "2": 0.30}
GOAL_PRIOR = {"over25": 0.55, "btts": 0.55}
COMMON = {"match_id": "1", "league_name": "L", "kickoff_time": datetime(2026, 10, 20, tzinfo=timezone.utc),
          "as_of": datetime(2026, 10, 19, tzinfo=timezone.utc), "pattern_hash": "x"}


def _blob(mc=40, r1=70.0, rx=15.0, r2=15.0, **kw):
    base = {"match_count": mc, "result_1_pct": r1, "result_x_pct": rx, "result_2_pct": r2,
            "ust_25_pct": 60.0, "kg_var_pct": 40.0, "dc_1x_pct": 85.0, "dc_x2_pct": 30.0, "dc_12_pct": 85.0}
    base.update(kw)
    return base


def test_rule_version_fingerprint_is_pinned():
    # Kural parametresi değişirse bu test kırılır: sabiti güncelle VE V4_RULE_VERSION'ı artır.
    assert (V4_RULE_VERSION, rule_params_fingerprint()) == ("ft-display-v4", "8d7677f5779f")


def test_publishes_home_pick_with_edge():
    picks = build_v4_recommendations({"pattern_ft_b": _blob(), "pattern_ft_c": _blob(mc=20)}, PRIOR)
    assert len(picks) == 1
    pick = picks[0]
    assert pick["recommendation_id"] == "ft-display-v4:result:1"
    assert pick["archive"] == "archive_1+archive_2"
    assert pick["archive_3_frequency_pct"] is None and pick["archive_3_match_count"] is None
    assert pick["calibrated_pct"] > pick["prior_pct"] + 5
    assert pick["confidence_tier"] in ("high", "medium", "low")


def test_abstains_on_small_pool():
    decision = decide_result({"pattern_ft_b": _blob(mc=12)}, PRIOR)
    assert decision["abstain_reason"] == "pooled_sample_below_minimum"


def test_excludes_draw_pick():
    decision = decide_result({"pattern_ft_b": _blob(r1=20, rx=60, r2=20, mc=80)}, PRIOR)
    assert decision["selection"] == "X" and decision["abstain_reason"] == "draw_excluded"


def test_abstains_without_edge():
    decision = decide_result({"pattern_ft_b": _blob(r1=46, rx=25, r2=29, mc=60)}, PRIOR)
    assert decision["abstain_reason"] == "edge_below_minimum"


def test_ignores_archives_below_ten_matches():
    assert decide_result({"pattern_ft_b": _blob(mc=9)}, PRIOR) == {"abstain_reason": "archive_sample_below_minimum"}


def test_ledger_rows_cover_top_pick_informational_and_market_summary():
    patterns = {"pattern_ft_b": _blob(), "pattern_ht_b": _blob(mc=30), "pattern_h2_b": _blob(mc=30)}
    rows = ledger_rows_v4(patterns, PRIOR, GOAL_PRIOR, COMMON)
    top = [r for r in rows if r["source"] == "top_pick" and not r.get("informational")]
    info = {r["market"]: r for r in rows if r.get("informational")}
    summary = [r for r in rows if r["source"] == "market_summary"]
    assert [r["selection"] for r in top] == ["1"]
    assert top[0]["baseline_selection"] == "1" and top[0]["confidence_tier"]
    assert info["ou_25"]["selection"] == "over" and info["kg"]["selection"] == "no"
    assert all(r["archive"] == "a1" for r in summary)
    assert {r["period"] for r in summary} == {"ht", "h2", "ft"}
    assert not any(r["market"] == "ou_25" and r["period"] != "ft" for r in summary)


def test_market_summary_tie_keeps_first_option_like_frontend():
    patterns = {"pattern_ft_b": _blob(r1=40, rx=40, r2=20)}
    rows = [r for r in ledger_rows_v4(patterns, PRIOR, GOAL_PRIOR, COMMON)
            if r["source"] == "market_summary" and r["market"] == "result"]
    assert rows[0]["selection"] == "1"


def test_module_constant_names():
    assert prematch_v4.MARKET_SUMMARY_RULE_VERSION == "market-summary-v1"


def test_hash_string_format_and_recommendation_hash():
    from app.analysis.persist import hash_string
    from app.api.services import _recommendation_hash
    assert hash_string({"b": "x1", "c": None, "d": "y2"}) == "b=x1;d=y2"
    assert hash_string({"b": None, "c": None, "d": None}) is None
    assert _recommendation_hash([{"market": "result", "pattern_hash": "b=x1"}]) == "b=x1"
    assert _recommendation_hash([{"market": "result"}]) is None
    assert _recommendation_hash([]) is None
