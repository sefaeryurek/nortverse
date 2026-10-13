"""evaluation.py çekirdek mantığı birim testleri."""

import pytest

from app.analysis.evaluation import (
    BASE_RESULT,
    LEAGUE_BASE_RATES,
    EvalAccumulator,
    PatternEval,
    brier_avg,
    evaluate_pattern,
    get_base_rates,
    pct,
)


# --- get_base_rates ---

def test_get_base_rates_known_league():
    rates = get_base_rates("English Premier League")
    assert rates["1"] == 45.2
    assert rates["X"] == 24.6

def test_get_base_rates_case_insensitive():
    rates = get_base_rates("english premier league")
    assert rates == LEAGUE_BASE_RATES["English Premier League"]

def test_get_base_rates_unknown_league():
    rates = get_base_rates("Unknown Fantasy League")
    assert rates is BASE_RESULT

def test_get_base_rates_none():
    rates = get_base_rates(None)
    assert rates is BASE_RESULT


# --- pct / brier_avg ---

def test_pct_normal():
    assert pct(7, 10) == 70.0

def test_pct_zero_total():
    assert pct(0, 0) == 0.0

def test_brier_avg_normal():
    assert brier_avg(1.5, 3) == 0.5

def test_brier_avg_zero():
    assert brier_avg(0.0, 0) is None


# --- evaluate_pattern ---

def test_evaluate_pattern_none_data():
    assert evaluate_pattern(None, "1", True, True) is None

def test_evaluate_pattern_empty_dict():
    assert evaluate_pattern({}, "1", True, True) is None

def test_evaluate_pattern_low_match_count():
    assert evaluate_pattern({"match_count": 2}, "1", True, True, min_matches=5) is None

def test_evaluate_pattern_basic():
    data = {
        "match_count": 20,
        "result_1_pct": 60.0,
        "result_x_pct": 20.0,
        "result_2_pct": 20.0,
        "ust_25_pct": 70.0,
        "kg_var_pct": 60.0,
    }
    pat = evaluate_pattern(data, "1", True, True, league_name="English Premier League")
    assert pat is not None
    assert isinstance(pat, PatternEval)
    assert pat.match_count == 20
    assert pat.result_pick == "1"
    assert pat.result_hit is True
    assert pat.brier_score >= 0

def test_evaluate_pattern_result_miss():
    data = {
        "match_count": 20,
        "result_1_pct": 60.0,
        "result_x_pct": 20.0,
        "result_2_pct": 20.0,
        "ust_25_pct": 70.0,
        "kg_var_pct": 60.0,
    }
    pat = evaluate_pattern(data, "2", True, True)
    assert pat is not None
    assert pat.result_pick == "1"
    assert pat.result_hit is False

def test_evaluate_pattern_over_25():
    data = {
        "match_count": 50,
        "result_1_pct": 40.0,
        "result_x_pct": 30.0,
        "result_2_pct": 30.0,
        "ust_25_pct": 80.0,
        "kg_var_pct": 30.0,
    }
    pat = evaluate_pattern(data, "1", True, False)
    assert pat is not None
    assert pat.over_25_pick == "Üst"
    assert pat.over_25_hit is True
    assert pat.btts_hit is True  # pick=Yok, actual=False → hit

def test_evaluate_pattern_brier_bounds():
    data = {
        "match_count": 10,
        "result_1_pct": 90.0,
        "result_x_pct": 5.0,
        "result_2_pct": 5.0,
        "ust_25_pct": 50.0,
        "kg_var_pct": 50.0,
    }
    pat = evaluate_pattern(data, "1", True, True)
    assert pat is not None
    assert 0 <= pat.brier_score <= 2.0

def test_evaluate_pattern_confident_margin():
    data = {
        "match_count": 100,
        "result_1_pct": 70.0,
        "result_x_pct": 15.0,
        "result_2_pct": 15.0,
        "ust_25_pct": 50.0,
        "kg_var_pct": 50.0,
    }
    pat = evaluate_pattern(data, "1", True, True)
    assert pat is not None
    assert pat.result_margin > 0


# --- EvalAccumulator ---

def test_accumulator_none():
    acc = EvalAccumulator()
    acc.accumulate(None)
    assert acc.evaluated == 0

def test_accumulator_basic():
    acc = EvalAccumulator()
    pat = PatternEval(
        match_count=10, result_pick="1", result_pct=60.0, result_hit=True,
        result_margin=15.0, is_confident=True,
        over_25_pick="Üst", over_25_pct=70.0, over_25_hit=True,
        btts_pick="KG Var", btts_pct=60.0, btts_hit=False,
        brier_score=0.3,
    )
    acc.accumulate(pat)
    assert acc.evaluated == 1
    assert acc.result_hit == 1
    assert acc.over_hit == 1
    assert acc.btts_hit == 0
    assert acc.confident_evaluated == 1
    assert acc.confident_result_hit == 1
    assert acc.brier_sum == 0.3

def test_accumulator_merge():
    a = EvalAccumulator(evaluated=5, result_hit=3, over_hit=2, btts_hit=1,
                        confident_evaluated=2, confident_result_hit=1, brier_sum=1.5)
    b = EvalAccumulator(evaluated=3, result_hit=1, over_hit=1, btts_hit=2,
                        confident_evaluated=1, confident_result_hit=0, brier_sum=0.9)
    a.merge(b)
    assert a.evaluated == 8
    assert a.result_hit == 4
    assert a.over_hit == 3
    assert a.btts_hit == 3
    assert a.confident_evaluated == 3
    assert a.confident_result_hit == 1
    assert abs(a.brier_sum - 2.4) < 0.001

def test_accumulator_not_confident():
    acc = EvalAccumulator()
    pat = PatternEval(
        match_count=10, result_pick="X", result_pct=30.0, result_hit=True,
        result_margin=3.0, is_confident=False,
        over_25_pick="Alt", over_25_pct=55.0, over_25_hit=True,
        btts_pick="KG Yok", btts_pct=55.0, btts_hit=True,
        brier_score=0.5,
    )
    acc.accumulate(pat)
    assert acc.evaluated == 1
    assert acc.confident_evaluated == 0
    assert acc.confident_result_hit == 0
