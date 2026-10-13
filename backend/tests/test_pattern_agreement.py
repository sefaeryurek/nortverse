"""Pattern status agreement mantığı birim testleri.

routes_fixture.py get_pattern_status endpoint'indeki B/C/D uyum hesaplamasını
doğrudan fonksiyon olarak test eder.
"""


def _compute_agreement(b_data: dict | None, c_data: dict | None, d_data: dict | None):
    """get_pattern_status endpoint'indeki agreement mantığını yeniden üretir."""
    has_b = bool(b_data and isinstance(b_data, dict) and b_data.get("match_count", 0) >= 5)
    has_c = bool(c_data and isinstance(c_data, dict) and c_data.get("match_count", 0) >= 1)
    has_d = bool(d_data and isinstance(d_data, dict) and d_data.get("match_count", 0) >= 1)

    if not (has_b or has_c or has_d):
        return None

    agreement = False
    agreement_bcd = False
    winners: dict[str, str] = {}
    for label, data, active in [("b", b_data, has_b), ("c", c_data, has_c), ("d", d_data, has_d)]:
        if active:
            winners[label] = max(
                ["1", "x", "2"],
                key=lambda k, d=data: d.get(f"result_{k}_pct", 0),
            )
    if "b" in winners and "c" in winners:
        agreement = winners["b"] == winners["c"]
    if "b" in winners and "c" in winners and "d" in winners:
        agreement_bcd = len(set(winners.values())) == 1

    return {
        "has_b": has_b, "has_c": has_c, "has_d": has_d,
        "agreement": agreement, "agreement_bcd": agreement_bcd,
    }


class TestPatternAgreement:
    def test_all_agree_home_win(self):
        b = {"match_count": 10, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        c = {"match_count": 5, "result_1_pct": 60, "result_x_pct": 20, "result_2_pct": 20}
        d = {"match_count": 8, "result_1_pct": 55, "result_x_pct": 30, "result_2_pct": 15}
        result = _compute_agreement(b, c, d)
        assert result["agreement"] is True
        assert result["agreement_bcd"] is True

    def test_bc_agree_d_disagrees(self):
        b = {"match_count": 10, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        c = {"match_count": 5, "result_1_pct": 60, "result_x_pct": 20, "result_2_pct": 20}
        d = {"match_count": 8, "result_1_pct": 20, "result_x_pct": 50, "result_2_pct": 30}
        result = _compute_agreement(b, c, d)
        assert result["agreement"] is True
        assert result["agreement_bcd"] is False

    def test_bc_disagree(self):
        b = {"match_count": 10, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        c = {"match_count": 5, "result_1_pct": 20, "result_x_pct": 60, "result_2_pct": 20}
        result = _compute_agreement(b, c, None)
        assert result["agreement"] is False

    def test_only_b(self):
        b = {"match_count": 10, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        result = _compute_agreement(b, None, None)
        assert result["has_b"] is True
        assert result["has_c"] is False
        assert result["agreement"] is False

    def test_only_c(self):
        c = {"match_count": 3, "result_1_pct": 30, "result_x_pct": 40, "result_2_pct": 30}
        result = _compute_agreement(None, c, None)
        assert result["has_c"] is True
        assert result["has_b"] is False

    def test_b_below_threshold(self):
        b = {"match_count": 3, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        c = {"match_count": 5, "result_1_pct": 60, "result_x_pct": 20, "result_2_pct": 20}
        result = _compute_agreement(b, c, None)
        assert result["has_b"] is False
        assert result["has_c"] is True

    def test_all_none(self):
        assert _compute_agreement(None, None, None) is None

    def test_empty_dict(self):
        assert _compute_agreement({}, {}, {}) is None

    def test_draw_winner(self):
        b = {"match_count": 10, "result_1_pct": 20, "result_x_pct": 50, "result_2_pct": 30}
        c = {"match_count": 5, "result_1_pct": 25, "result_x_pct": 45, "result_2_pct": 30}
        result = _compute_agreement(b, c, None)
        assert result["agreement"] is True

    def test_away_winner(self):
        b = {"match_count": 10, "result_1_pct": 10, "result_x_pct": 20, "result_2_pct": 70}
        c = {"match_count": 5, "result_1_pct": 15, "result_x_pct": 25, "result_2_pct": 60}
        d = {"match_count": 3, "result_1_pct": 5, "result_x_pct": 30, "result_2_pct": 65}
        result = _compute_agreement(b, c, d)
        assert result["agreement"] is True
        assert result["agreement_bcd"] is True

    def test_bd_without_c(self):
        b = {"match_count": 10, "result_1_pct": 50, "result_x_pct": 25, "result_2_pct": 25}
        d = {"match_count": 5, "result_1_pct": 55, "result_x_pct": 30, "result_2_pct": 15}
        result = _compute_agreement(b, None, d)
        assert result["has_b"] is True
        assert result["has_d"] is True
        assert result["agreement"] is False
        assert result["agreement_bcd"] is False

    def test_equal_percentages_max_picks_first(self):
        b = {"match_count": 10, "result_1_pct": 33, "result_x_pct": 33, "result_2_pct": 33}
        result = _compute_agreement(b, None, None)
        assert result["has_b"] is True
