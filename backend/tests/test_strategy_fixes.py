"""Strateji katmanı düzeltmeleri: %50 altı seçim yok, ensemble beraberlik anahtarı."""

from app.analysis.ensemble import _extract_pattern_features
from app.analysis.evaluation import evaluate_pattern


def _pattern(over: float, btts: float) -> dict:
    return {"match_count": 200, "result_1_pct": 45.0, "result_x_pct": 25.0, "result_2_pct": 30.0,
            "ust_25_pct": over, "kg_var_pct": btts}


def test_goal_picks_never_below_fifty_percent():
    # Lig baz oranı ~%55 iken ham %52 Üst: eski kural "Alt %48" seçiyordu.
    ev = evaluate_pattern(_pattern(52.0, 53.0), "1", True, True, league_name="English Premier League")
    assert ev.over_25_pick == "Üst" and ev.over_25_pct >= 50
    assert ev.btts_pick == "KG Var" and ev.btts_pct >= 50


def test_ensemble_missing_pattern_uses_draw_base_rate():
    feats = _extract_pattern_features(None, ["result_1_pct", "result_x_pct", "result_2_pct"],
                                      {"1": 45.0, "X": 25.0, "2": 30.0})
    assert feats == [45.0, 25.0, 30.0]
