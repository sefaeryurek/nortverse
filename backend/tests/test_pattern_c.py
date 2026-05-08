"""Sprint 8.10 — Pattern C correctness testleri.

`_ratios_match` fuzzy match (tolerance > 0) için. tolerance == 0 yolu
DB-side JSONB equality yapar — ayrı integration test gerektirir.
"""

import pytest

from app.analysis.pattern_c import _ratios_match


class TestRatiosMatch:
    """Tolerance > 0 fuzzy match davranışı (yavaş yol)."""

    def test_exact_match_zero_tolerance(self) -> None:
        a = {"1-0": 4.0, "2-0": 3.5}
        b = {"1-0": 4.0, "2-0": 3.5}
        assert _ratios_match(a, b, 0.0) is True

    def test_within_tolerance(self) -> None:
        a = {"1-0": 4.0, "2-0": 3.5}
        b = {"1-0": 4.5, "2-0": 3.0}  # Hepsi ±0.5 içinde
        assert _ratios_match(a, b, 0.5) is True

    def test_exceeds_tolerance(self) -> None:
        a = {"1-0": 4.0, "2-0": 3.5}
        b = {"1-0": 4.0, "2-0": 2.5}  # 2-0 farkı 1.0 > 0.5
        assert _ratios_match(a, b, 0.5) is False

    def test_missing_key_in_candidate(self) -> None:
        a = {"1-0": 4.0, "2-0": 3.5}
        b = {"1-0": 4.0}  # 2-0 eksik
        assert _ratios_match(a, b, 0.5) is False

    def test_zero_tolerance_strict(self) -> None:
        a = {"1-0": 4.0}
        b = {"1-0": 4.5}  # 0.5 fark, tolerance=0 reddetmeli
        assert _ratios_match(a, b, 0.0) is False

    def test_empty_target_passes(self) -> None:
        # Boş target — döngü çalışmaz, True döner
        assert _ratios_match({}, {"1-0": 4.0}, 0.5) is True


# Not: tolerance=0 yolu DB-side JSONB equality kullanır.
# Bu yol için integration test (gerçek Postgres) gerekir; sentetik
# unit test mümkün değil. self-test CLI canlı doğrulama yapar.
