"""Korelasyon faktörleri testleri — Poisson model ve yardımcı fonksiyonlar."""

from app.analysis.correlation import (
    _outcomes_for_score,
    compute_from_matches,
    compute_poisson_correlations,
    get_correction_factor,
)


class TestOutcomesForScore:
    def test_0_0(self):
        out = _outcomes_for_score(0, 0)
        assert "result:X" in out
        assert "kg:KG Yok" in out
        assert "ou_25:Alt 2.5" in out
        assert "fark:Berabere" in out
        assert "ev_05:Ev Alt 0.5" in out
        assert "dep_05:Dep Alt 0.5" in out

    def test_2_1(self):
        out = _outcomes_for_score(2, 1)
        assert "result:1" in out
        assert "kg:KG Var" in out
        assert "ou_25:Üst 2.5" in out
        assert "fark:Ev 1 fark" in out
        assert "ev_15:Ev Üst 1.5" in out
        assert "dep_05:Dep Üst 0.5" in out

    def test_0_3(self):
        out = _outcomes_for_score(0, 3)
        assert "result:2" in out
        assert "ou_35:Alt 3.5" in out
        assert "fark:Dep 3+ fark" in out
        assert "ev_05:Ev Alt 0.5" in out

    def test_1_1(self):
        out = _outcomes_for_score(1, 1)
        assert "result:X" in out
        assert "dc:1X" in out
        assert "dc:X2" in out
        assert "kg:KG Var" in out
        assert "ou_25:Alt 2.5" in out
        assert "ou_15:Üst 1.5" in out


class TestPoissonCorrelations:
    def test_returns_dict(self):
        corr = compute_poisson_correlations()
        assert isinstance(corr, dict)
        assert len(corr) > 200

    def test_known_positive_correlation(self):
        corr = compute_poisson_correlations()
        assert corr["kg:KG Var|ou_25:Üst 2.5"] > 1.0

    def test_known_negative_correlation(self):
        corr = compute_poisson_correlations()
        assert corr["kg:KG Var|ou_25:Alt 2.5"] < 1.0

    def test_no_trivial_entries(self):
        corr = compute_poisson_correlations()
        for key, val in corr.items():
            assert abs(val - 1.0) > 0.01

    def test_key_format(self):
        corr = compute_poisson_correlations()
        for key in corr:
            assert "|" in key
            parts = key.split("|")
            assert len(parts) == 2
            assert parts[0] < parts[1]


class TestGetCorrectionFactor:
    def test_known_pair(self):
        corr = compute_poisson_correlations()
        factor = get_correction_factor(corr, "kg", "KG Var", "ou_25", "Üst 2.5")
        assert factor > 1.0

    def test_reversed_order(self):
        corr = compute_poisson_correlations()
        f1 = get_correction_factor(corr, "kg", "KG Var", "ou_25", "Üst 2.5")
        f2 = get_correction_factor(corr, "ou_25", "Üst 2.5", "kg", "KG Var")
        assert f1 == f2

    def test_unknown_pair_returns_1(self):
        corr = compute_poisson_correlations()
        factor = get_correction_factor(corr, "unknown_market", "sel_a", "another", "sel_b")
        assert factor == 1.0


class TestComputeFromMatches:
    def test_empty_list_falls_back_to_poisson(self):
        result = compute_from_matches([])
        poisson = compute_poisson_correlations()
        assert result == poisson

    def test_under_100_falls_back_to_poisson(self):
        matches = [{"actual_ft_home": 1, "actual_ft_away": 0} for _ in range(50)]
        result = compute_from_matches(matches)
        poisson = compute_poisson_correlations()
        assert result == poisson

    def test_skips_invalid_scores(self):
        matches = [
            {"actual_ft_home": None, "actual_ft_away": 0},
            {"actual_ft_home": -1, "actual_ft_away": 0},
            {"actual_ft_home": 1, "actual_ft_away": 50},
        ]
        result = compute_from_matches(matches)
        poisson = compute_poisson_correlations()
        assert result == poisson

    def test_with_enough_data(self):
        matches = []
        for h in range(5):
            for a in range(5):
                matches.extend([{"actual_ft_home": h, "actual_ft_away": a}] * 5)
        assert len(matches) == 125
        result = compute_from_matches(matches)
        assert isinstance(result, dict)
        assert len(result) > 0
