"""Gölge → ekran terfi ölçütleri (Sprint 94 P3)."""

from app.cli.league_cmds import evaluate_promotion


def _good() -> dict:
    return {
        "canonical": True, "seasons": ["2026/2027", "2025/2026", "2024/2025", "2023/2024", "2022/2023"],
        "recent_coverage": (99.0, 97.0), "h2h_pass_pct": 72.0, "score_delay_p90_h": 4.0, "odds_coverage_pct": 95.0,
        "backtest_prematch": {"n": 400, "hit_pct": 60.0, "shown_pct": 59.0},
        "backtest_live": {"n": 1500, "hit_pct": 92.0, "shown_pct": 93.0},
        "shadow_prematch": {"pool": {"resolved": 140, "verdict": "on_track"},
                            "league": {"resolved": 35, "below": False, "hit_pct": 60.0, "avg_prob_pct": 58.0}},
        "shadow_live": {"pool": {"resolved": 220, "verdict": "above"},
                        "league": {"resolved": 40, "below": False, "hit_pct": 95.0, "avg_prob_pct": 92.0}},
    }


def _failed(m: dict) -> set[str]:
    return {c["name"] for c in evaluate_promotion(m) if not c["ok"]}


def test_all_criteria_met():
    assert _failed(_good()) == set()


def test_each_criterion_can_fail():
    cases = {
        "sezon": {"seasons": ["2026/2027", "2025/2026"]},
        "λ_ve_A3": {"recent_coverage": (99.0, 80.0)},
        "h2h_gecisi": {"h2h_pass_pct": 53.0},
        "skor_gecikmesi": {"score_delay_p90_h": 9.5},
        "lig_adi": {"canonical": False},
        "oran_kapsamasi": {"odds_coverage_pct": 40.0},
        "backtest_mac_oncesi": {"backtest_prematch": {"n": 400, "hit_pct": 55.0, "shown_pct": 59.0}},  # fark 4 puan
        "backtest_canli": {"backtest_live": {"n": 120, "hit_pct": 92.0, "shown_pct": 92.0}},          # az karar
    }
    for name, override in cases.items():
        assert _failed({**_good(), **override}) == {name}, name


def test_shadow_scorecard_requires_pool_verdict_and_league_floor():
    m = _good()
    m["shadow_live"] = {"pool": {"resolved": 220, "verdict": "below"}, "league": m["shadow_live"]["league"]}
    assert _failed(m) == {"golge_canli"}
    m = _good()
    m["shadow_prematch"] = {"pool": m["shadow_prematch"]["pool"],
                            "league": {"resolved": 35, "below": True, "hit_pct": 40.0, "avg_prob_pct": 58.0}}
    assert _failed(m) == {"golge_mac_oncesi"}


def test_missing_measurements_are_not_passes():
    checks = {c["name"]: c["ok"] for c in evaluate_promotion({"canonical": True, "seasons": []})}
    assert checks["λ_ve_A3"] is None and checks["h2h_gecisi"] is None and checks["oran_kapsamasi"] is None
    assert checks["backtest_canli"] is False
