"""Günlük değerlendirme (routes_evaluation) birim testleri."""

from __future__ import annotations

import pytest

from app.api.routes_evaluation import _evaluate_pattern, _pct


# ─── _pct ──────────────────────────────────────────────────────────────────────

class TestPct:
    def test_basic(self):
        assert _pct(3, 10) == 30.0

    def test_zero_total(self):
        assert _pct(0, 0) == 0.0

    def test_all_hit(self):
        assert _pct(5, 5) == 100.0

    def test_rounding(self):
        assert _pct(1, 3) == 33.3


# ─── _evaluate_pattern ────────────────────────────────────────────────────────

class TestEvaluatePattern:
    def test_none_data(self):
        assert _evaluate_pattern(None, "1", True, True) is None

    def test_empty_dict(self):
        assert _evaluate_pattern({}, "1", True, True) is None

    def test_zero_match_count(self):
        assert _evaluate_pattern({"match_count": 0}, "1", True, True) is None

    def test_result_hit(self):
        data = {
            "match_count": 50,
            "result_1_pct": 55.0,
            "result_x_pct": 25.0,
            "result_2_pct": 20.0,
            "ust_25_pct": 60.0,
            "kg_var_pct": 45.0,
        }
        result = _evaluate_pattern(data, "1", True, False)
        assert result is not None
        assert result.result_pick == "1"
        assert result.result_hit is True
        assert result.result_pct == 55.0

    def test_result_miss(self):
        data = {
            "match_count": 50,
            "result_1_pct": 55.0,
            "result_x_pct": 25.0,
            "result_2_pct": 20.0,
            "ust_25_pct": 60.0,
            "kg_var_pct": 45.0,
        }
        result = _evaluate_pattern(data, "2", True, False)
        assert result is not None
        assert result.result_pick == "1"
        assert result.result_hit is False

    def test_over_25_hit(self):
        data = {
            "match_count": 30,
            "result_1_pct": 40.0,
            "result_x_pct": 30.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 65.0,
            "kg_var_pct": 50.0,
        }
        result = _evaluate_pattern(data, "1", True, False)
        assert result is not None
        assert result.over_25_pick == "Üst"
        assert result.over_25_hit is True
        assert result.over_25_pct == 65.0

    def test_over_25_miss(self):
        data = {
            "match_count": 30,
            "result_1_pct": 40.0,
            "result_x_pct": 30.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 65.0,
            "kg_var_pct": 50.0,
        }
        result = _evaluate_pattern(data, "1", False, False)
        assert result is not None
        assert result.over_25_pick == "Üst"
        assert result.over_25_hit is False

    def test_under_25_pick(self):
        data = {
            "match_count": 30,
            "result_1_pct": 40.0,
            "result_x_pct": 30.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 35.0,
            "kg_var_pct": 50.0,
        }
        result = _evaluate_pattern(data, "1", False, False)
        assert result is not None
        assert result.over_25_pick == "Alt"
        assert result.over_25_hit is True
        assert result.over_25_pct == 65.0

    def test_btts_hit(self):
        data = {
            "match_count": 20,
            "result_1_pct": 40.0,
            "result_x_pct": 30.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 50.0,
            "kg_var_pct": 70.0,
        }
        result = _evaluate_pattern(data, "1", True, True)
        assert result is not None
        assert result.btts_pick == "KG Var"
        assert result.btts_hit is True

    def test_btts_miss(self):
        data = {
            "match_count": 20,
            "result_1_pct": 40.0,
            "result_x_pct": 30.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 50.0,
            "kg_var_pct": 70.0,
        }
        result = _evaluate_pattern(data, "1", True, False)
        assert result is not None
        assert result.btts_pick == "KG Var"
        assert result.btts_hit is False

    def test_no_btts_pick(self):
        data = {
            "match_count": 20,
            "result_1_pct": 40.0,
            "result_x_pct": 30.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 50.0,
            "kg_var_pct": 30.0,
        }
        result = _evaluate_pattern(data, "1", True, False)
        assert result is not None
        assert result.btts_pick == "KG Yok"
        assert result.btts_hit is True

    def test_draw_result(self):
        data = {
            "match_count": 50,
            "result_1_pct": 30.0,
            "result_x_pct": 40.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 50.0,
            "kg_var_pct": 50.0,
        }
        result = _evaluate_pattern(data, "X", False, False)
        assert result is not None
        assert result.result_pick == "X"
        assert result.result_hit is True

    def test_away_win_result(self):
        data = {
            "match_count": 50,
            "result_1_pct": 20.0,
            "result_x_pct": 30.0,
            "result_2_pct": 50.0,
            "ust_25_pct": 50.0,
            "kg_var_pct": 50.0,
        }
        result = _evaluate_pattern(data, "2", False, False)
        assert result is not None
        assert result.result_pick == "2"
        assert result.result_hit is True

    def test_none_pct_treated_as_zero(self):
        data = {
            "match_count": 10,
            "result_1_pct": None,
            "result_x_pct": None,
            "result_2_pct": None,
            "ust_25_pct": None,
            "kg_var_pct": None,
        }
        result = _evaluate_pattern(data, "1", False, False)
        assert result is not None

    def test_non_dict_data(self):
        assert _evaluate_pattern("invalid", "1", True, True) is None
        assert _evaluate_pattern(42, "1", True, True) is None
        assert _evaluate_pattern([], "1", True, True) is None
