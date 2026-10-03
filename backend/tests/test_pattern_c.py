"""Sprint 8.10 — Pattern C correctness testleri.

`_ratios_match` fuzzy match (tolerance > 0) için. tolerance == 0 yolu
DB-side JSONB equality yapar — ayrı integration test gerektirir.
"""


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

    def test_empty_target_does_not_match_every_archive_row(self) -> None:
        assert _ratios_match({}, {"1-0": 4.0}, 0.5) is False


# Not: tolerance=0 yolu DB-side JSONB equality kullanır.
# Bu yol için integration test (gerçek Postgres) gerekir; sentetik
# unit test mümkün değil. self-test CLI canlı doğrulama yapar.


import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from app.analysis.pattern_c import find_pattern_c_adaptive
from app.analysis.pattern_stats import PatternResult


def _make_pattern_result(match_count: int) -> PatternResult:
    """Minimal PatternResult stub."""
    return MagicMock(spec=PatternResult, match_count=match_count)


@pytest.mark.asyncio
async def test_adaptive_returns_first_sufficient_tolerance():
    """İlk yeterli tolerance'ta durmalı, daha fazla artırmamalı."""
    call_count = 0
    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc)

    async def mock_find(ft_ratios, min_matches=1, tolerance=0.0,
                        exclude_match_id=None, as_of=None):
        nonlocal call_count
        call_count += 1
        if tolerance >= 0.75:
            r = _make_pattern_result(5)
            return (r, r, r)
        return (None, None, None)

    with patch("app.analysis.pattern_c.find_pattern_c_all_periods", side_effect=mock_find):
        result = await find_pattern_c_adaptive(
            {"1-0": 4.0}, min_matches=3,
            base_tolerance=0.5, max_tolerance=1.0, tolerance_step=0.25,
            as_of=as_of,
        )
    assert result[2] is not None
    assert result[2].match_count == 5
    assert call_count == 2


@pytest.mark.asyncio
async def test_adaptive_returns_max_tolerance_result_when_never_sufficient():
    """Hiçbir tolerance yetmezse max_tolerance sonucunu döndürür."""
    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc)

    async def mock_find(ft_ratios, min_matches=1, tolerance=0.0,
                        exclude_match_id=None, as_of=None):
        r = _make_pattern_result(1)
        return (r, r, r)

    with patch("app.analysis.pattern_c.find_pattern_c_all_periods", side_effect=mock_find):
        result = await find_pattern_c_adaptive(
            {"1-0": 4.0}, min_matches=5,
            base_tolerance=0.5, max_tolerance=1.0, tolerance_step=0.25,
            as_of=as_of,
        )
    assert result[2] is not None
    assert result[2].match_count == 1


@pytest.mark.asyncio
async def test_adaptive_base_tolerance_sufficient_no_escalation():
    """Base tolerance yeterliyse tek çağrı yapılır."""
    call_count = 0
    as_of = datetime(2026, 1, 1, tzinfo=timezone.utc)

    async def mock_find(ft_ratios, min_matches=1, tolerance=0.0,
                        exclude_match_id=None, as_of=None):
        nonlocal call_count
        call_count += 1
        r = _make_pattern_result(10)
        return (r, r, r)

    with patch("app.analysis.pattern_c.find_pattern_c_all_periods", side_effect=mock_find):
        result = await find_pattern_c_adaptive(
            {"1-0": 4.0}, min_matches=3,
            base_tolerance=0.5, max_tolerance=1.0, tolerance_step=0.25,
            as_of=as_of,
        )
    assert result[2].match_count == 10
    assert call_count == 1
