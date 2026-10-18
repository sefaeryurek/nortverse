"""Pattern status agreement mantığı birim testleri.

routes_fixture.pattern_status (gerçek kod) — eşik maç öncesi v4 ile aynı: her arşiv ≥10 maç.
"""


from app.api.routes_fixture import pattern_status as _compute_agreement


class TestPatternAgreement:
    def test_all_agree_home_win(self):
        b = {"match_count": 10, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        c = {"match_count": 12, "result_1_pct": 60, "result_x_pct": 20, "result_2_pct": 20}
        d = {"match_count": 15, "result_1_pct": 55, "result_x_pct": 30, "result_2_pct": 15}
        result = _compute_agreement(b, c, d)
        assert result["agreement"] is True
        assert result["agreement_bcd"] is True

    def test_bc_agree_d_disagrees(self):
        b = {"match_count": 10, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        c = {"match_count": 12, "result_1_pct": 60, "result_x_pct": 20, "result_2_pct": 20}
        d = {"match_count": 15, "result_1_pct": 20, "result_x_pct": 50, "result_2_pct": 30}
        result = _compute_agreement(b, c, d)
        assert result["agreement"] is True
        assert result["agreement_bcd"] is False

    def test_bc_disagree(self):
        b = {"match_count": 10, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        c = {"match_count": 12, "result_1_pct": 20, "result_x_pct": 60, "result_2_pct": 20}
        result = _compute_agreement(b, c, None)
        assert result["agreement"] is False

    def test_only_b(self):
        b = {"match_count": 10, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        result = _compute_agreement(b, None, None)
        assert result["has_b"] is True
        assert result["has_c"] is False
        assert result["agreement"] is False

    def test_only_c(self):
        c = {"match_count": 10, "result_1_pct": 30, "result_x_pct": 40, "result_2_pct": 30}
        result = _compute_agreement(None, c, None)
        assert result["has_c"] is True
        assert result["has_b"] is False

    def test_b_below_threshold(self):
        b = {"match_count": 3, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        c = {"match_count": 12, "result_1_pct": 60, "result_x_pct": 20, "result_2_pct": 20}
        result = _compute_agreement(b, c, None)
        assert result["has_b"] is False
        assert result["has_c"] is True

    def test_all_none(self):
        assert _compute_agreement(None, None, None) is None

    def test_empty_dict(self):
        assert _compute_agreement({}, {}, {}) is None

    def test_draw_winner(self):
        b = {"match_count": 10, "result_1_pct": 20, "result_x_pct": 50, "result_2_pct": 30}
        c = {"match_count": 12, "result_1_pct": 25, "result_x_pct": 45, "result_2_pct": 30}
        result = _compute_agreement(b, c, None)
        assert result["agreement"] is True

    def test_away_winner(self):
        b = {"match_count": 10, "result_1_pct": 10, "result_x_pct": 20, "result_2_pct": 70}
        c = {"match_count": 12, "result_1_pct": 15, "result_x_pct": 25, "result_2_pct": 60}
        d = {"match_count": 10, "result_1_pct": 5, "result_x_pct": 30, "result_2_pct": 65}
        result = _compute_agreement(b, c, d)
        assert result["agreement"] is True
        assert result["agreement_bcd"] is True

    def test_bd_without_c(self):
        b = {"match_count": 10, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        d = {"match_count": 11, "result_1_pct": 55, "result_x_pct": 30, "result_2_pct": 15}
        result = _compute_agreement(b, None, d)
        assert result["has_b"] is True
        assert result["has_d"] is True
        assert result["agreement"] is False
        assert result["agreement_bcd"] is False

    def test_equal_percentages_max_picks_first(self):
        b = {"match_count": 10, "result_1_pct": 33, "result_x_pct": 33, "result_2_pct": 33}
        result = _compute_agreement(b, None, None)
        assert result["has_b"] is True

    def test_small_samples_do_not_earn_a_badge(self):
        """v4 ile aynı eşik: 9 maçlık A2/A3 rozet almaz (eskiden 1 maç yetiyordu)."""
        b = {"match_count": 9, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        c = {"match_count": 9, "result_1_pct": 60, "result_x_pct": 20, "result_2_pct": 20}
        d = {"match_count": 1, "result_1_pct": 60, "result_x_pct": 20, "result_2_pct": 20}
        assert _compute_agreement(b, c, d) is None
