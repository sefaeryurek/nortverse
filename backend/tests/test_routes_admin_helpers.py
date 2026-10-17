"""routes_admin.py yardımcı fonksiyon birim testleri."""

import math
import pytest

from app.analysis.stats_utils import wilson_ci, paired_coverage_interval


class TestWilsonCI:
    def test_basic(self):
        lo, hi = wilson_ci(50, 100)
        assert 0.35 < lo < 0.45
        assert 0.55 < hi < 0.65

    def test_perfect(self):
        lo, hi = wilson_ci(100, 100)
        assert lo > 0.95
        assert hi >= 0.99

    def test_zero_successes(self):
        lo, hi = wilson_ci(0, 100)
        assert lo == 0.0
        assert hi < 0.05

    def test_zero_trials(self):
        assert wilson_ci(0, 0) is None

    def test_negative_trials(self):
        assert wilson_ci(5, -1) is None

    def test_small_sample(self):
        lo, hi = wilson_ci(1, 2)
        assert 0 < lo < hi < 1

    def test_custom_z(self):
        lo_95, hi_95 = wilson_ci(50, 100, z=1.96)
        lo_99, hi_99 = wilson_ci(50, 100, z=2.576)
        assert lo_99 < lo_95
        assert hi_99 > hi_95

    def test_symmetry(self):
        lo, hi = wilson_ci(50, 100)
        mid = (lo + hi) / 2
        assert abs(mid - 0.5) < 0.02


class TestPairedCoverageInterval:
    def test_basic(self):
        diff, lo, hi = paired_coverage_interval(30, 20, 100)
        assert diff == 10.0
        assert lo < diff < hi

    def test_zero_paired(self):
        assert paired_coverage_interval(5, 3, 0) is None

    def test_equal_model_baseline(self):
        diff, lo, hi = paired_coverage_interval(10, 10, 50)
        assert diff == 0.0
        assert lo < 0 < hi

    def test_model_dominant(self):
        diff, lo, hi = paired_coverage_interval(40, 5, 100)
        assert diff == 35.0
        assert lo > 0

    def test_baseline_dominant(self):
        diff, lo, hi = paired_coverage_interval(5, 40, 100)
        assert diff == -35.0
        assert hi < 0

    def test_bounds_clamped(self):
        diff, lo, hi = paired_coverage_interval(0, 0, 1)
        assert lo >= -100.0
        assert hi <= 100.0
