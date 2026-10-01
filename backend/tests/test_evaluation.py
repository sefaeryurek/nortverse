"""Günlük değerlendirme (routes_evaluation) birim testleri."""

from __future__ import annotations

import pytest

from app.api.routes_evaluation import _evaluate_pattern, _pct
from app.config import AnalysisConfig


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


# ─── Beraberlik (X) shrinkage ───────────────────────────────────────────────────
#
# Not: BASE_RESULT = {"1": 44.4, "X": 24.6, "2": 30.9} — "1" popülasyonda en
# yüksek taban orana sahip. Additive shrink formülü (raw*(1-s) + base*s) her
# zaman "1"i güçlendirdiği için X, zaten armgax olmadığı bir senaryoda asla
# devreye giremiyor (base_X üç değerin en küçüğü). Aşağıdaki testler bu
# matematiksel gerçeği doğru şekilde yansıtır: shrinkage küçük örneklemde
# çoğunluk sınıfına (genelde "1") doğru regresyon yapıyor, X'i armgax yapmıyor.
class TestDrawShrinkage:
    def test_small_sample_regresses_toward_dominant_base_rate(self):
        """mc=5 (yüksek shrink) — ham argmax '2' (42%) iken taban oranı en
        yüksek olan '1' (base=44.4) shrink sonrası öne geçer."""
        data = {
            "match_count": 5,
            "result_1_pct": 38.0,
            "result_x_pct": 20.0,
            "result_2_pct": 42.0,
            "ust_25_pct": 50.0,
            "kg_var_pct": 50.0,
        }
        result = _evaluate_pattern(data, "1", False, False)
        assert result is not None
        # Ham veride "2" (42%) en yüksekti; shrink sonrası "1" öne geçiyor.
        assert result.result_pick == "1"
        assert result.result_hit is True

    def test_large_sample_preserves_raw_argmax(self):
        """Aynı ham yüzdeler ama mc=500 (düşük shrink) — ham argmax '2' korunur."""
        data = {
            "match_count": 500,
            "result_1_pct": 38.0,
            "result_x_pct": 20.0,
            "result_2_pct": 42.0,
            "ust_25_pct": 50.0,
            "kg_var_pct": 50.0,
        }
        result = _evaluate_pattern(data, "2", False, False)
        assert result is not None
        assert result.result_pick == "2"
        assert result.result_hit is True

    def test_small_sample_flip_is_sample_size_dependent(self):
        """Aynı ham dağılım (38/20/42) küçük örneklemde '1', büyük örneklemde
        '2' seçtiriyor — shrink miktarı match_count'a bağlı (mc arttıkça azalır)."""
        small = _evaluate_pattern(
            {
                "match_count": 5,
                "result_1_pct": 38.0,
                "result_x_pct": 20.0,
                "result_2_pct": 42.0,
                "ust_25_pct": 50.0,
                "kg_var_pct": 50.0,
            },
            "1",
            False,
            False,
        )
        large = _evaluate_pattern(
            {
                "match_count": 500,
                "result_1_pct": 38.0,
                "result_x_pct": 20.0,
                "result_2_pct": 42.0,
                "ust_25_pct": 50.0,
                "kg_var_pct": 50.0,
            },
            "1",
            False,
            False,
        )
        assert small is not None and large is not None
        assert small.result_pick != large.result_pick

    def test_near_tied_pcts_resolve_to_highest_base_rate_not_draw(self):
        """35/35/30 (1 ve X ham veride eşit) — shrink sonrası '1' netleşerek
        kazanır; X'in taban oranı (24.6) üçü içinde en düşük olduğundan bu
        additive formülle asla armgax olamaz (matematiksel olarak imkansız:
        base_X < base_1 ve base_X < base_2)."""
        data = {
            "match_count": 5,
            "result_1_pct": 35.0,
            "result_x_pct": 35.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 50.0,
            "kg_var_pct": 50.0,
        }
        result = _evaluate_pattern(data, "1", False, False)
        assert result is not None
        assert result.result_pick == "1"
        assert result.result_hit is True

        result_x_actual = _evaluate_pattern(data, "X", False, False)
        assert result_x_actual is not None
        assert result_x_actual.result_pick == "1"
        assert result_x_actual.result_hit is False

    def test_zero_match_count_edge_case_no_division_error(self):
        """match_count=1 (fonksiyonun kabul ettiği en düşük değer) — shrink
        formülü (SHRINKAGE / (1 + mc/20)) sıfıra bölme hatası vermemeli."""
        data = {
            "match_count": 1,
            "result_1_pct": 50.0,
            "result_x_pct": 30.0,
            "result_2_pct": 20.0,
            "ust_25_pct": 50.0,
            "kg_var_pct": 50.0,
        }
        result = _evaluate_pattern(data, "1", False, False)
        assert result is not None
        assert result.result_pick == "1"

    def test_below_min_matches_returns_none(self):
        data = {
            "match_count": 3,
            "result_1_pct": 100.0,
            "result_x_pct": 0.0,
            "result_2_pct": 0.0,
            "ust_25_pct": 100.0,
            "kg_var_pct": 0.0,
        }
        assert _evaluate_pattern(data, "1", True, False, min_matches=5) is None

    def test_at_min_matches_returns_evaluation(self):
        data = {
            "match_count": 5,
            "result_1_pct": 60.0,
            "result_x_pct": 20.0,
            "result_2_pct": 20.0,
            "ust_25_pct": 60.0,
            "kg_var_pct": 40.0,
        }
        result = _evaluate_pattern(data, "1", True, False, min_matches=5)
        assert result is not None
        assert result.match_count == 5
        assert result.result_pick == "1"
        assert result.result_hit is True


# ─── Kalibre edilmiş eşikler (over_25_threshold / btts_threshold) ─────────────

class TestCalibratedThresholds:
    """Sistem %59.8 Üst / %61.6 KG Var tahmin ediyordu ama gerçek oran %55.4 idi
    (sistematik önyargı — sonuçlar naif baseline'ın altına düşüyordu). Eşikler
    50'den kalibre edilmiş taban orana (55.0) çekildi — pattern verisi popülasyon
    ortalamasının üzerinde göstermedikçe "Üst"/"KG Var" tahmin edilmez.
    """

    def test_default_base_rates(self):
        cfg = AnalysisConfig()
        assert cfg.over_25_base_rate == 55.0
        assert cfg.btts_base_rate == 56.0

    def test_low_ust_predicts_alt_after_shrinkage(self, monkeypatch):
        # Shrinkage + baz oran (55%) ile 45% gözlem → adjusted ~46.9% < 50 → "Alt"
        monkeypatch.setattr(
            "app.api.routes_evaluation.ANALYSIS",
            AnalysisConfig(over_25_base_rate=55.0, btts_base_rate=56.0,
                           result_shrinkage=0.45),
        )
        data = {
            "match_count": 30,
            "result_1_pct": 40.0,
            "result_x_pct": 30.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 45.0,
            "kg_var_pct": 50.0,
        }
        result = _evaluate_pattern(data, "1", False, False)
        assert result is not None
        assert result.over_25_pick == "Alt"

    def test_pattern_56_still_predicts_over(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.routes_evaluation.ANALYSIS",
            AnalysisConfig(),
        )
        data = {
            "match_count": 30,
            "result_1_pct": 40.0,
            "result_x_pct": 30.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 56.0,
            "kg_var_pct": 50.0,
        }
        result = _evaluate_pattern(data, "1", True, False)
        assert result is not None
        assert result.over_25_pick == "Üst"
        assert result.over_25_hit is True

    def test_low_btts_predicts_no_after_shrinkage(self, monkeypatch):
        # Shrinkage + baz oran (56%) ile 44% gözlem → adjusted ~46.5% < 50 → "KG Yok"
        monkeypatch.setattr(
            "app.api.routes_evaluation.ANALYSIS",
            AnalysisConfig(over_25_base_rate=55.0, btts_base_rate=56.0,
                           result_shrinkage=0.45),
        )
        data = {
            "match_count": 30,
            "result_1_pct": 40.0,
            "result_x_pct": 30.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 50.0,
            "kg_var_pct": 44.0,
        }
        result = _evaluate_pattern(data, "1", False, False)
        assert result is not None
        assert result.btts_pick == "KG Yok"

    def test_btts_above_base_rate_predicts_yes(self, monkeypatch):
        monkeypatch.setattr(
            "app.api.routes_evaluation.ANALYSIS",
            AnalysisConfig(btts_base_rate=56.0),
        )
        data = {
            "match_count": 30,
            "result_1_pct": 40.0,
            "result_x_pct": 30.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 50.0,
            "kg_var_pct": 65.0,
        }
        result = _evaluate_pattern(data, "1", False, True)
        assert result is not None
        assert result.btts_pick == "KG Var"
        assert result.btts_hit is True

    def test_base_rate_override_via_config(self, monkeypatch):
        # Düşük baz oran (40%) — pattern 35% → adjusted < 40 → "Alt"
        monkeypatch.setattr(
            "app.api.routes_evaluation.ANALYSIS",
            AnalysisConfig(over_25_base_rate=40.0, btts_base_rate=40.0,
                           result_shrinkage=0.45),
        )
        data = {
            "match_count": 30,
            "result_1_pct": 40.0,
            "result_x_pct": 30.0,
            "result_2_pct": 30.0,
            "ust_25_pct": 35.0,
            "kg_var_pct": 35.0,
        }
        result = _evaluate_pattern(data, "1", False, False)
        assert result is not None
        assert result.over_25_pick == "Alt"
        assert result.btts_pick == "KG Yok"


class TestMarginAndConfident:
    def test_high_margin_is_confident(self):
        data = {
            "match_count": 50,
            "result_1_pct": 60.0,
            "result_x_pct": 20.0,
            "result_2_pct": 20.0,
            "ust_25_pct": 55.0,
            "kg_var_pct": 55.0,
        }
        result = _evaluate_pattern(data, "1", True, True)
        assert result is not None
        assert result.result_margin > 0
        assert result.is_confident is True

    def test_low_margin_not_confident(self):
        data = {
            "match_count": 50,
            "result_1_pct": 35.0,
            "result_x_pct": 33.0,
            "result_2_pct": 32.0,
            "ust_25_pct": 55.0,
            "kg_var_pct": 55.0,
        }
        result = _evaluate_pattern(data, "X", False, False)
        assert result is not None
        assert result.result_margin < 8.0
        assert result.is_confident is False

    def test_league_base_rates_german(self):
        data = {
            "match_count": 30,
            "result_1_pct": 45.0,
            "result_x_pct": 30.0,
            "result_2_pct": 25.0,
            "ust_25_pct": 55.0,
            "kg_var_pct": 55.0,
        }
        result = _evaluate_pattern(
            data, "1", True, True, league_name="German Bundesliga"
        )
        assert result is not None
        assert result.result_pick == "1"

    def test_league_base_rates_unknown_falls_back(self):
        data = {
            "match_count": 30,
            "result_1_pct": 45.0,
            "result_x_pct": 30.0,
            "result_2_pct": 25.0,
            "ust_25_pct": 55.0,
            "kg_var_pct": 55.0,
        }
        result_known = _evaluate_pattern(
            data, "1", True, True, league_name="German Bundesliga"
        )
        result_unknown = _evaluate_pattern(
            data, "1", True, True, league_name="Unknown League"
        )
        assert result_known is not None
        assert result_unknown is not None
