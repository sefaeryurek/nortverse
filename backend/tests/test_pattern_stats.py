"""pattern_stats.compute_stats kapsamlı testleri.

~130 istatistik alanını elle hesaplanmış değerlerle doğrular.
Mock satırlar SimpleNamespace ile oluşturulur — DB bağımlılığı yok.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.analysis.pattern_stats import PatternResult, _hnd_result, compute_stats


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _row(ft_h: int, ft_a: int, ht_h: int | None = None, ht_a: int | None = None):
    """actual_* alanları olan mock maç satırı."""
    h2_h = (ft_h - ht_h) if ht_h is not None else None
    h2_a = (ft_a - ht_a) if ht_a is not None else None
    return SimpleNamespace(
        actual_ft_home=ft_h, actual_ft_away=ft_a,
        actual_ht_home=ht_h, actual_ht_away=ht_a,
        actual_h2_home=h2_h, actual_h2_away=h2_a,
    )


# ---------------------------------------------------------------------------
# _hnd_result birim testleri
# ---------------------------------------------------------------------------

class TestHndResult:
    """Handikap sonucu hesaplama — convention Sprint 7'de düzeltildi."""

    def test_no_handicap(self):
        assert _hnd_result(2, 1, 0, 0) == "1"
        assert _hnd_result(1, 1, 0, 0) == "x"
        assert _hnd_result(0, 1, 0, 0) == "2"

    def test_home_plus_2(self):
        # Hnd(2:0) → ev +2 alır → eff_h = h+2
        assert _hnd_result(0, 1, 2, 0) == "1"   # 2-1 → ev kazanır
        assert _hnd_result(0, 2, 2, 0) == "x"   # 2-2 → berabere
        assert _hnd_result(0, 3, 2, 0) == "2"   # 2-3 → dep kazanır

    def test_home_plus_1(self):
        # Hnd(1:0) → ev +1 alır
        assert _hnd_result(1, 1, 1, 0) == "1"   # 2-1 → ev
        assert _hnd_result(0, 1, 1, 0) == "x"   # 1-1 → berabere
        assert _hnd_result(0, 2, 1, 0) == "2"   # 1-2 → dep

    def test_away_plus_1(self):
        # Hnd(0:1) → dep +1 alır
        assert _hnd_result(1, 0, 0, 1) == "x"   # 1-1 → berabere
        assert _hnd_result(2, 0, 0, 1) == "1"   # 2-1 → ev
        assert _hnd_result(0, 0, 0, 1) == "2"   # 0-1 → dep

    def test_away_plus_2(self):
        # Hnd(0:2) → dep +2 alır
        assert _hnd_result(1, 0, 0, 2) == "2"   # 1-2 → dep kazanır
        assert _hnd_result(2, 0, 0, 2) == "x"   # 2-2 → berabere
        assert _hnd_result(3, 0, 0, 2) == "1"   # 3-2 → ev kazanır


# ---------------------------------------------------------------------------
# compute_stats — temel davranışlar
# ---------------------------------------------------------------------------

class TestComputeStatsEdgeCases:

    def test_empty_list_returns_none(self):
        assert compute_stats([], "ft") is None

    def test_invalid_period_raises(self):
        with pytest.raises(ValueError, match="Invalid period"):
            compute_stats([_row(1, 0)], "xx")

    def test_valid_periods(self):
        rows = [_row(1, 0, 0, 0)]
        for period in ("ft", "ht", "h2"):
            result = compute_stats(rows, period)
            assert result is not None

    def test_returns_pattern_result(self):
        result = compute_stats([_row(1, 0)], "ft")
        assert isinstance(result, PatternResult)

    def test_invalid_scores_skipped(self):
        bad = SimpleNamespace(
            actual_ft_home=-1, actual_ft_away=0,
            actual_ht_home=None, actual_ht_away=None,
            actual_h2_home=None, actual_h2_away=None,
        )
        assert compute_stats([bad], "ft") is None

    def test_match_count(self):
        rows = [_row(1, 0), _row(0, 1), _row(2, 2)]
        result = compute_stats(rows, "ft")
        assert result.match_count == 3


# ---------------------------------------------------------------------------
# Tek maç — tüm alanları doğrula (2-1 FT, 1-0 HT)
# ---------------------------------------------------------------------------

class TestSingleMatch:
    """FT 2-1, HT 1-0 → H2 1-1. Tek maç = her şey %100 veya %0."""

    @pytest.fixture()
    def result(self):
        return compute_stats([_row(2, 1, 1, 0)], "ft")

    # Maç Sonucu
    def test_result(self, result):
        assert result.result_1_pct == 100.0
        assert result.result_x_pct == 0.0
        assert result.result_2_pct == 0.0

    # Çifte Şans
    def test_double_chance(self, result):
        assert result.dc_1x_pct == 100.0
        assert result.dc_x2_pct == 0.0
        assert result.dc_12_pct == 100.0

    # Alt/Üst — toplam 3 gol
    def test_over_under(self, result):
        assert result.alt_15_pct == 0.0    # 3 >= 2, üst
        assert result.ust_15_pct == 100.0
        assert result.alt_25_pct == 0.0    # 3 >= 3, üst
        assert result.ust_25_pct == 100.0
        assert result.alt_35_pct == 100.0  # 3 < 4, alt
        assert result.ust_35_pct == 0.0

    # KG
    def test_btts(self, result):
        assert result.kg_var_pct == 100.0  # 2>0 ve 1>0
        assert result.kg_yok_pct == 0.0

    # Handikap (2:0) → ev +2: 4-1 → ev kazanır
    def test_handicap_h20(self, result):
        assert result.hnd_h20_1_pct == 100.0
        assert result.hnd_h20_x_pct == 0.0
        assert result.hnd_h20_2_pct == 0.0

    # Handikap (1:0) → ev +1: 3-1 → ev kazanır
    def test_handicap_h10(self, result):
        assert result.hnd_h10_1_pct == 100.0

    # Handikap (0:1) → dep +1: 2-2 → berabere
    def test_handicap_a10(self, result):
        assert result.hnd_a10_1_pct == 0.0
        assert result.hnd_a10_x_pct == 100.0
        assert result.hnd_a10_2_pct == 0.0

    # Handikap (0:2) → dep +2: 2-3 → dep kazanır
    def test_handicap_a20(self, result):
        assert result.hnd_a20_1_pct == 0.0
        assert result.hnd_a20_x_pct == 0.0
        assert result.hnd_a20_2_pct == 100.0

    # MS + 1.5 kombine — ev kazanır + üst 1.5 (3 gol >= 2)
    def test_ms_15_combo(self, result):
        assert result.ms1_ust15_pct == 100.0
        assert result.ms1_alt15_pct == 0.0
        assert result.msx_ust15_pct == 0.0
        assert result.ms2_ust15_pct == 0.0

    # MS + 2.5 kombine — ev kazanır + üst 2.5 (3 gol >= 3)
    def test_ms_25_combo(self, result):
        assert result.ms1_ust25_pct == 100.0
        assert result.ms1_alt25_pct == 0.0

    # MS + KG kombine — ev kazanır + KG var
    def test_ms_kg_combo(self, result):
        assert result.ms1_kg_var_pct == 100.0
        assert result.ms1_kg_yok_pct == 0.0
        assert result.msx_kg_var_pct == 0.0
        assert result.ms2_kg_var_pct == 0.0

    # Fark — 2-1 = ev 1 fark
    def test_margin(self, result):
        assert result.fark_ev1_pct == 100.0
        assert result.fark_ev2_pct == 0.0
        assert result.fark_ev3p_pct == 0.0
        assert result.fark_ber_pct == 0.0
        assert result.fark_dep1_pct == 0.0

    # Taraf Alt/Üst — ev 2 gol, dep 1 gol
    def test_side_totals(self, result):
        assert result.ev_ust_05_pct == 100.0   # 2 >= 1
        assert result.ev_ust_15_pct == 100.0   # 2 >= 2
        assert result.ev_ust_25_pct == 0.0     # 2 < 3
        assert result.ev_alt_25_pct == 100.0
        assert result.dep_ust_05_pct == 100.0  # 1 >= 1
        assert result.dep_ust_15_pct == 0.0    # 1 < 2
        assert result.dep_alt_15_pct == 100.0

    # Gol aralığı — 3 gol → 2-3 aralığı
    def test_goal_range(self, result):
        assert result.gol_01_pct == 0.0
        assert result.gol_23_pct == 100.0
        assert result.gol_45_pct == 0.0
        assert result.gol_6p_pct == 0.0

    # Score freq
    def test_score_freq(self, result):
        assert result.score_freq == {"2-1": 1}

    # HT alt istatistikleri — HT 1-0
    def test_ht_sub_stats(self, result):
        assert result.ht_result_1_pct == 100.0
        assert result.ht_result_x_pct == 0.0
        assert result.ht_result_2_pct == 0.0
        assert result.ht_alt_15_pct == 100.0   # 1 gol < 2
        assert result.ht_ust_15_pct == 0.0
        assert result.ht_kg_var_pct == 0.0     # 1-0 → KG yok
        assert result.ht_kg_yok_pct == 100.0

    # H2 alt istatistikleri — H2 1-1
    def test_h2_sub_stats(self, result):
        assert result.h2_result_1_pct == 0.0
        assert result.h2_result_x_pct == 100.0
        assert result.h2_result_2_pct == 0.0
        assert result.h2_kg_var_pct == 100.0
        assert result.h2_kg_yok_pct == 0.0

    # İY/MS kombine — HT ev kazanır, FT ev kazanır → 1/1
    def test_iy_ms_combo(self, result):
        assert result.iy_ms_11_pct == 100.0
        assert result.iy_ms_1x_pct == 0.0
        assert result.iy_ms_12_pct == 0.0

    # En çok gol olacak yarı — HT 1 gol, H2 2 gol → 2. yarı
    def test_most_goals_half(self, result):
        assert result.encok_gol_1y_pct == 0.0
        assert result.encok_gol_esit_pct == 0.0
        assert result.encok_gol_2y_pct == 100.0

    # İki yarıda da üst 1.5 — HT 1 gol < 2, H2 2 gol >= 2 → hayır
    def test_both_halves_over_15(self, result):
        assert result.iki_yari_ust15_pct == 0.0
        assert result.iki_yari_alt15_pct == 0.0  # HT alt ama H2 üst → ikisi de sağlanmaz

    # Ev iki yarıda da gol — HT ev 1, H2 ev 1 → evet
    def test_home_both_halves_score(self, result):
        assert result.ev_iki_yari_gol_pct == 100.0

    # Dep iki yarıda da gol — HT dep 0, H2 dep 1 → hayır
    def test_away_both_halves_score(self, result):
        assert result.dep_iki_yari_gol_pct == 0.0

    # İY/H2 KG kombine — HT KG yok (1-0), H2 KG var (1-1) → yv
    def test_iy_h2_kg_combo(self, result):
        assert result.iy_h2_kg_yv_pct == 100.0
        assert result.iy_h2_kg_vv_pct == 0.0
        assert result.iy_h2_kg_vy_pct == 0.0
        assert result.iy_h2_kg_yy_pct == 0.0

    # İY alt/üst — HT 1 gol
    def test_iy_over_under(self, result):
        assert result.iy_ust_05_pct == 100.0   # 1 >= 1
        assert result.iy_alt_05_pct == 0.0
        assert result.iy_ust_15_pct == 0.0     # 1 < 2
        assert result.iy_alt_15_pct == 100.0

    # Ev HT alt/üst — ev HT 1 gol
    def test_ev_ht_over_under(self, result):
        assert result.ev_ht_ust_05_pct == 100.0  # 1 >= 1
        assert result.ev_ht_alt_05_pct == 0.0

    # Dep HT alt/üst — dep HT 0 gol
    def test_dep_ht_over_under(self, result):
        assert result.dep_ht_ust_05_pct == 0.0   # 0 < 1
        assert result.dep_ht_alt_05_pct == 100.0

    # Ev hangi yarıda daha çok gol — HT ev 1, H2 ev 1 → eşit
    def test_home_most_goals_half(self, result):
        assert result.ev_encok_esit_pct == 100.0
        assert result.ev_encok_1y_pct == 0.0
        assert result.ev_encok_2y_pct == 0.0

    # Dep hangi yarıda daha çok gol — HT dep 0, H2 dep 1 → 2. yarı
    def test_away_most_goals_half(self, result):
        assert result.dep_encok_2y_pct == 100.0
        assert result.dep_encok_1y_pct == 0.0
        assert result.dep_encok_esit_pct == 0.0


# ---------------------------------------------------------------------------
# İki maç — yüzde hesabı
# ---------------------------------------------------------------------------

class TestTwoMatches:
    """(2-1) + (0-0) → result_1=50%, result_x=50%."""

    @pytest.fixture()
    def result(self):
        return compute_stats([_row(2, 1), _row(0, 0)], "ft")

    def test_match_count(self, result):
        assert result.match_count == 2

    def test_result_percentages(self, result):
        assert result.result_1_pct == 50.0
        assert result.result_x_pct == 50.0
        assert result.result_2_pct == 0.0

    def test_btts(self, result):
        assert result.kg_var_pct == 50.0   # 2-1 var, 0-0 yok
        assert result.kg_yok_pct == 50.0

    def test_over_under_25(self, result):
        assert result.ust_25_pct == 50.0   # 3 gol, 0 gol
        assert result.alt_25_pct == 50.0


# ---------------------------------------------------------------------------
# Üç maç — eşit dağılım
# ---------------------------------------------------------------------------

class TestThreeMatches:
    """(2-0) + (1-1) + (0-2) → her sonuç %33.3."""

    @pytest.fixture()
    def result(self):
        return compute_stats([_row(2, 0), _row(1, 1), _row(0, 2)], "ft")

    def test_result_thirds(self, result):
        assert result.result_1_pct == 33.3
        assert result.result_x_pct == 33.3
        assert result.result_2_pct == 33.3

    def test_double_chance(self, result):
        assert result.dc_1x_pct == 66.7
        assert result.dc_x2_pct == 66.7
        assert result.dc_12_pct == 66.7


# ---------------------------------------------------------------------------
# Tamamlayıcı çiftler %100 tutarlılığı
# ---------------------------------------------------------------------------

class TestComplementarySums:
    """Tüm tamamlayıcı çiftler %100'e tamamlanmalı (yuvarlama toleransı ±0.2)."""

    @pytest.fixture()
    def result(self):
        rows = [
            _row(3, 1, 1, 0),
            _row(0, 0, 0, 0),
            _row(1, 2, 0, 1),
            _row(2, 2, 1, 1),
            _row(4, 0, 2, 0),
        ]
        return compute_stats(rows, "ft")

    def test_result_sum(self, result):
        s = result.result_1_pct + result.result_x_pct + result.result_2_pct
        assert abs(s - 100.0) < 0.5

    def test_over_under_15(self, result):
        assert abs(result.alt_15_pct + result.ust_15_pct - 100.0) < 0.5

    def test_over_under_25(self, result):
        assert abs(result.alt_25_pct + result.ust_25_pct - 100.0) < 0.5

    def test_over_under_35(self, result):
        assert abs(result.alt_35_pct + result.ust_35_pct - 100.0) < 0.5

    def test_btts_sum(self, result):
        assert abs(result.kg_var_pct + result.kg_yok_pct - 100.0) < 0.5

    def test_handicap_h20_sum(self, result):
        s = result.hnd_h20_1_pct + result.hnd_h20_x_pct + result.hnd_h20_2_pct
        assert abs(s - 100.0) < 0.5

    def test_handicap_h10_sum(self, result):
        s = result.hnd_h10_1_pct + result.hnd_h10_x_pct + result.hnd_h10_2_pct
        assert abs(s - 100.0) < 0.5

    def test_handicap_a10_sum(self, result):
        s = result.hnd_a10_1_pct + result.hnd_a10_x_pct + result.hnd_a10_2_pct
        assert abs(s - 100.0) < 0.5

    def test_handicap_a20_sum(self, result):
        s = result.hnd_a20_1_pct + result.hnd_a20_x_pct + result.hnd_a20_2_pct
        assert abs(s - 100.0) < 0.5

    def test_side_home_05(self, result):
        assert abs(result.ev_alt_05_pct + result.ev_ust_05_pct - 100.0) < 0.5

    def test_side_home_15(self, result):
        assert abs(result.ev_alt_15_pct + result.ev_ust_15_pct - 100.0) < 0.5

    def test_side_away_05(self, result):
        assert abs(result.dep_alt_05_pct + result.dep_ust_05_pct - 100.0) < 0.5

    def test_goal_ranges_sum(self, result):
        s = result.gol_01_pct + result.gol_23_pct + result.gol_45_pct + result.gol_6p_pct
        assert abs(s - 100.0) < 0.5

    def test_margin_sum(self, result):
        s = (result.fark_ev1_pct + result.fark_ev2_pct + result.fark_ev3p_pct +
             result.fark_ber_pct +
             result.fark_dep1_pct + result.fark_dep2_pct + result.fark_dep3p_pct)
        assert abs(s - 100.0) < 0.5

    def test_ht_result_sum(self, result):
        s = result.ht_result_1_pct + result.ht_result_x_pct + result.ht_result_2_pct
        assert abs(s - 100.0) < 0.5

    def test_h2_result_sum(self, result):
        s = result.h2_result_1_pct + result.h2_result_x_pct + result.h2_result_2_pct
        assert abs(s - 100.0) < 0.5

    def test_encok_gol_sum(self, result):
        s = result.encok_gol_1y_pct + result.encok_gol_esit_pct + result.encok_gol_2y_pct
        assert abs(s - 100.0) < 0.5


# ---------------------------------------------------------------------------
# Alt/Üst sınır değerleri
# ---------------------------------------------------------------------------

class TestOverUnderBoundaries:

    def test_one_goal_all_under(self):
        result = compute_stats([_row(1, 0)], "ft")
        assert result.alt_15_pct == 100.0  # 1 < 2
        assert result.alt_25_pct == 100.0  # 1 < 3
        assert result.alt_35_pct == 100.0  # 1 < 4

    def test_two_goals_boundary(self):
        result = compute_stats([_row(1, 1)], "ft")
        assert result.ust_15_pct == 100.0  # 2 >= 2 → üst
        assert result.alt_25_pct == 100.0  # 2 < 3 → alt
        assert result.alt_35_pct == 100.0  # 2 < 4 → alt

    def test_three_goals_boundary(self):
        result = compute_stats([_row(2, 1)], "ft")
        assert result.ust_15_pct == 100.0  # 3 >= 2
        assert result.ust_25_pct == 100.0  # 3 >= 3
        assert result.alt_35_pct == 100.0  # 3 < 4

    def test_four_goals_all_over(self):
        result = compute_stats([_row(3, 1)], "ft")
        assert result.ust_15_pct == 100.0
        assert result.ust_25_pct == 100.0
        assert result.ust_35_pct == 100.0


# ---------------------------------------------------------------------------
# KG var/yok
# ---------------------------------------------------------------------------

class TestBTTS:

    def test_both_score(self):
        result = compute_stats([_row(1, 1)], "ft")
        assert result.kg_var_pct == 100.0

    def test_one_side_zero(self):
        result = compute_stats([_row(2, 0)], "ft")
        assert result.kg_yok_pct == 100.0

    def test_both_zero(self):
        result = compute_stats([_row(0, 0)], "ft")
        assert result.kg_yok_pct == 100.0


# ---------------------------------------------------------------------------
# Fark hesabı
# ---------------------------------------------------------------------------

class TestMargin:

    def test_home_1(self):
        result = compute_stats([_row(2, 1)], "ft")
        assert result.fark_ev1_pct == 100.0

    def test_home_2(self):
        result = compute_stats([_row(3, 1)], "ft")
        assert result.fark_ev2_pct == 100.0

    def test_home_3_plus(self):
        result = compute_stats([_row(3, 0)], "ft")
        assert result.fark_ev3p_pct == 100.0

    def test_draw(self):
        result = compute_stats([_row(1, 1)], "ft")
        assert result.fark_ber_pct == 100.0

    def test_away_1(self):
        result = compute_stats([_row(0, 1)], "ft")
        assert result.fark_dep1_pct == 100.0

    def test_away_2(self):
        result = compute_stats([_row(1, 3)], "ft")
        assert result.fark_dep2_pct == 100.0

    def test_away_3_plus(self):
        result = compute_stats([_row(0, 4)], "ft")
        assert result.fark_dep3p_pct == 100.0


# ---------------------------------------------------------------------------
# Gol aralıkları
# ---------------------------------------------------------------------------

class TestGoalRanges:

    def test_zero_goals(self):
        result = compute_stats([_row(0, 0)], "ft")
        assert result.gol_01_pct == 100.0

    def test_one_goal(self):
        result = compute_stats([_row(1, 0)], "ft")
        assert result.gol_01_pct == 100.0

    def test_two_goals(self):
        result = compute_stats([_row(1, 1)], "ft")
        assert result.gol_23_pct == 100.0

    def test_three_goals(self):
        result = compute_stats([_row(2, 1)], "ft")
        assert result.gol_23_pct == 100.0

    def test_four_goals(self):
        result = compute_stats([_row(2, 2)], "ft")
        assert result.gol_45_pct == 100.0

    def test_five_goals(self):
        result = compute_stats([_row(3, 2)], "ft")
        assert result.gol_45_pct == 100.0

    def test_six_plus_goals(self):
        result = compute_stats([_row(4, 3)], "ft")
        assert result.gol_6p_pct == 100.0


# ---------------------------------------------------------------------------
# Score freq
# ---------------------------------------------------------------------------

class TestScoreFreq:

    def test_single_score(self):
        result = compute_stats([_row(1, 0)], "ft")
        assert result.score_freq == {"1-0": 1}

    def test_most_common_first(self):
        rows = [_row(1, 0), _row(1, 0), _row(2, 1)]
        result = compute_stats(rows, "ft")
        keys = list(result.score_freq.keys())
        assert keys[0] == "1-0"
        assert result.score_freq["1-0"] == 2

    def test_max_12_scores(self):
        rows = [_row(i, 0) for i in range(15)]
        result = compute_stats(rows, "ft")
        assert len(result.score_freq) <= 12


# ---------------------------------------------------------------------------
# HT ve H2 period'larında compute_stats
# ---------------------------------------------------------------------------

class TestHTperiod:

    def test_ht_period_basic(self):
        result = compute_stats([_row(2, 1, 1, 0)], "ht")
        assert result.result_1_pct == 100.0
        assert result.match_count == 1

    def test_ht_period_no_ht_data(self):
        result = compute_stats([_row(2, 1)], "ht")
        assert result is None


class TestH2period:

    def test_h2_period_basic(self):
        result = compute_stats([_row(3, 1, 1, 0)], "h2")
        # H2 = 3-1 - 1-0 = 2-1 → ev kazanır
        assert result.result_1_pct == 100.0
        assert result.match_count == 1


# ---------------------------------------------------------------------------
# FT period'da HT/H2 alt istatistikleri
# ---------------------------------------------------------------------------

class TestFTsubStats:
    """FT period'da HT ve H2 alt istatistikleri hesaplanır."""

    def test_ht_sub_stats_in_ft(self):
        rows = [
            _row(3, 1, 2, 0),  # HT 2-0 → ev kazanır
            _row(1, 1, 0, 1),  # HT 0-1 → dep kazanır
        ]
        result = compute_stats(rows, "ft")
        assert result.ht_result_1_pct == 50.0
        assert result.ht_result_2_pct == 50.0

    def test_h2_sub_stats_in_ft(self):
        rows = [
            _row(3, 1, 2, 0),  # H2 1-1 → berabere
            _row(1, 1, 0, 1),  # H2 1-0 → ev kazanır
        ]
        result = compute_stats(rows, "ft")
        assert result.h2_result_x_pct == 50.0
        assert result.h2_result_1_pct == 50.0

    def test_no_ht_data_defaults_zero(self):
        result = compute_stats([_row(2, 1)], "ft")
        assert result.ht_result_1_pct == 0.0
        assert result.ht_result_x_pct == 0.0
        assert result.ht_result_2_pct == 0.0

    def test_ht_dc_in_ft(self):
        rows = [
            _row(2, 0, 1, 0),  # HT 1-0 → ev
            _row(0, 1, 0, 0),  # HT 0-0 → berabere
            _row(1, 3, 0, 2),  # HT 0-2 → dep
        ]
        result = compute_stats(rows, "ft")
        assert result.ht_dc_1x_pct == 66.7  # ev + ber = 2/3
        assert result.ht_dc_x2_pct == 66.7  # ber + dep = 2/3
        assert result.ht_dc_12_pct == 66.7  # ev + dep = 2/3


# ---------------------------------------------------------------------------
# İY/MS kombinasyonu
# ---------------------------------------------------------------------------

class TestIYMS:

    def test_iy_ms_11(self):
        # HT ev kazanır (1-0), FT ev kazanır (2-1) → 1/1
        result = compute_stats([_row(2, 1, 1, 0)], "ft")
        assert result.iy_ms_11_pct == 100.0

    def test_iy_ms_x2(self):
        # HT berabere (0-0), FT dep kazanır (0-1) → X/2
        result = compute_stats([_row(0, 1, 0, 0)], "ft")
        assert result.iy_ms_x2_pct == 100.0

    def test_iy_ms_21(self):
        # HT dep kazanır (0-1), FT ev kazanır (3-1) → 2/1 (comeback)
        result = compute_stats([_row(3, 1, 0, 1)], "ft")
        assert result.iy_ms_21_pct == 100.0


# ---------------------------------------------------------------------------
# En çok gol olacak yarı
# ---------------------------------------------------------------------------

class TestMostGoalsHalf:

    def test_first_half_more(self):
        # HT 2-1 = 3 gol, H2 0-0 = 0 gol → 1. yarı
        result = compute_stats([_row(2, 1, 2, 1)], "ft")
        assert result.encok_gol_1y_pct == 100.0

    def test_second_half_more(self):
        # HT 0-0 = 0 gol, H2 2-1 = 3 gol → 2. yarı
        result = compute_stats([_row(2, 1, 0, 0)], "ft")
        assert result.encok_gol_2y_pct == 100.0

    def test_equal_halves(self):
        # HT 1-0 = 1 gol, H2 0-1 = 1 gol → eşit
        result = compute_stats([_row(1, 1, 1, 0)], "ft")
        assert result.encok_gol_esit_pct == 100.0


# ---------------------------------------------------------------------------
# İki yarıda da üst 1.5
# ---------------------------------------------------------------------------

class TestBothHalvesOver15:

    def test_both_over(self):
        # HT 2-0 = 2 gol >= 2, H2 1-1 = 2 gol >= 2 → iki yarı üst
        result = compute_stats([_row(3, 1, 2, 0)], "ft")
        assert result.iki_yari_ust15_pct == 100.0

    def test_both_under(self):
        # HT 1-0 = 1 gol < 2, H2 0-0 = 0 gol < 2 → iki yarı alt
        result = compute_stats([_row(1, 0, 1, 0)], "ft")
        assert result.iki_yari_alt15_pct == 100.0

    def test_mixed_halves_neither(self):
        # HT 2-0 = 2 >= 2 (üst), H2 0-0 = 0 < 2 (alt) → ne alt ne üst
        result = compute_stats([_row(2, 0, 2, 0)], "ft")
        assert result.iki_yari_ust15_pct == 0.0
        assert result.iki_yari_alt15_pct == 0.0


# ---------------------------------------------------------------------------
# İY/H2 KG kombinasyonu
# ---------------------------------------------------------------------------

class TestIYH2KGCombo:

    def test_vv(self):
        # HT 1-1 (KG var), H2 1-1 (KG var) → vv
        result = compute_stats([_row(2, 2, 1, 1)], "ft")
        assert result.iy_h2_kg_vv_pct == 100.0

    def test_vy(self):
        # HT 1-1 (KG var), H2 1-0 (KG yok) → vy
        result = compute_stats([_row(2, 1, 1, 1)], "ft")
        assert result.iy_h2_kg_vy_pct == 100.0

    def test_yv(self):
        # HT 1-0 (KG yok), H2 1-1 (KG var) → yv
        result = compute_stats([_row(2, 1, 1, 0)], "ft")
        assert result.iy_h2_kg_yv_pct == 100.0

    def test_yy(self):
        # HT 1-0 (KG yok), H2 1-0 (KG yok) → yy
        result = compute_stats([_row(2, 0, 1, 0)], "ft")
        assert result.iy_h2_kg_yy_pct == 100.0


# ---------------------------------------------------------------------------
# Ev/Dep iki yarıda da gol
# ---------------------------------------------------------------------------

class TestBothHalvesGoal:

    def test_home_both_halves(self):
        # HT ev 1, H2 ev 1 → evet
        result = compute_stats([_row(2, 0, 1, 0)], "ft")
        assert result.ev_iki_yari_gol_pct == 100.0

    def test_home_only_first_half(self):
        # HT ev 1, H2 ev 0 → hayır
        result = compute_stats([_row(1, 1, 1, 0)], "ft")
        assert result.ev_iki_yari_gol_pct == 0.0

    def test_away_both_halves(self):
        # HT dep 1, H2 dep 1 → evet
        result = compute_stats([_row(0, 2, 0, 1)], "ft")
        assert result.dep_iki_yari_gol_pct == 100.0


# ---------------------------------------------------------------------------
# Ev/Dep hangi yarıda daha çok gol atar
# ---------------------------------------------------------------------------

class TestSideMostGoalsHalf:

    def test_home_first_half_more(self):
        # HT ev 2, H2 ev 1 → 1. yarı
        result = compute_stats([_row(3, 0, 2, 0)], "ft")
        assert result.ev_encok_1y_pct == 100.0

    def test_home_second_half_more(self):
        # HT ev 0, H2 ev 2 → 2. yarı
        result = compute_stats([_row(2, 0, 0, 0)], "ft")
        assert result.ev_encok_2y_pct == 100.0

    def test_home_equal(self):
        # HT ev 1, H2 ev 1 → eşit
        result = compute_stats([_row(2, 0, 1, 0)], "ft")
        assert result.ev_encok_esit_pct == 100.0

    def test_away_second_half_more(self):
        # HT dep 0, H2 dep 2 → 2. yarı
        result = compute_stats([_row(0, 2, 0, 0)], "ft")
        assert result.dep_encok_2y_pct == 100.0


# ---------------------------------------------------------------------------
# _period_scores doğrulama
# ---------------------------------------------------------------------------

class TestPeriodScoresValidation:

    def test_negative_score_skipped(self):
        bad = SimpleNamespace(
            actual_ft_home=-1, actual_ft_away=0,
            actual_ht_home=None, actual_ht_away=None,
            actual_h2_home=None, actual_h2_away=None,
        )
        assert compute_stats([bad], "ft") is None

    def test_score_over_30_skipped(self):
        bad = SimpleNamespace(
            actual_ft_home=31, actual_ft_away=0,
            actual_ht_home=None, actual_ht_away=None,
            actual_h2_home=None, actual_h2_away=None,
        )
        assert compute_stats([bad], "ft") is None

    def test_ht_greater_than_ft_skipped(self):
        # HT 3-0 > FT 2-0 → tutarsız → HT datası None
        row = SimpleNamespace(
            actual_ft_home=2, actual_ft_away=0,
            actual_ht_home=3, actual_ht_away=0,
            actual_h2_home=None, actual_h2_away=None,
        )
        result = compute_stats([row], "ht")
        assert result is None

    def test_mixed_valid_invalid(self):
        good = _row(1, 0)
        bad = SimpleNamespace(
            actual_ft_home=None, actual_ft_away=0,
            actual_ht_home=None, actual_ht_away=None,
            actual_h2_home=None, actual_h2_away=None,
        )
        result = compute_stats([good, bad], "ft")
        assert result.match_count == 1
