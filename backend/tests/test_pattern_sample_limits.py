from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.analysis import pattern_b, pattern_c
from app.db.models import Match


def mock_archive(monkeypatch, module, rows):
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session = AsyncMock()
    session.execute.return_value = result

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(module, "get_session", get_session)
    return session


@pytest.mark.asyncio
async def test_pattern_b_threshold_uses_valid_sample(monkeypatch):
    rows = [Match(actual_ft_home=1, actual_ft_away=0) for _ in range(4)]
    rows.append(Match(actual_ft_home=-1, actual_ft_away=0))
    mock_archive(monkeypatch, pattern_b, rows)
    assert await pattern_b.find_pattern_b_matches("ft", ["1-0"], [], []) is None


@pytest.mark.asyncio
async def test_pattern_c_checks_each_period_sample(monkeypatch):
    rows = [Match(actual_ft_home=1, actual_ft_away=0, actual_ht_home=0,
                  actual_ht_away=0, actual_h2_home=1, actual_h2_away=0),
            Match(actual_ft_home=2, actual_ft_away=0)]
    mock_archive(monkeypatch, pattern_c, rows)
    ht, h2, ft = await pattern_c.find_pattern_c_all_periods({"1-0": 3.5}, min_matches=2)
    assert ht is None and h2 is None
    assert ft.match_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("minimum", [0, -1, 1.5, True])
async def test_invalid_sample_limit_fails_before_database(minimum):
    with pytest.raises(ValueError, match="positive integer"):
        await pattern_b.find_pattern_b_matches("ft", [], [], [], min_matches=minimum)
    with pytest.raises(ValueError, match="positive integer"):
        await pattern_c.find_pattern_c_all_periods({"1-0": 3.5}, min_matches=minimum)


@pytest.mark.asyncio
@pytest.mark.parametrize("tolerance", [-1, float("nan"), float("inf")])
async def test_invalid_tolerance_fails_before_database(tolerance):
    with pytest.raises(ValueError, match="tolerance"):
        await pattern_c.find_pattern_c_all_periods({"1-0": 3.5}, tolerance=tolerance)


@pytest.mark.parametrize("candidate", [
    {"1-0": float("nan")}, {"1-0": float("inf")}, {"1-0": -1},
    {"1-0": "3.5"}, {"1-0": 3.5, "2-0": 4},
])
def test_fuzzy_match_rejects_invalid_or_different_ratio_sets(candidate):
    assert not pattern_c._ratios_match({"1-0": 3.5}, candidate, 0.5)


@pytest.mark.asyncio
async def test_empty_ratios_do_not_query_entire_archive(monkeypatch):
    session = mock_archive(monkeypatch, pattern_c, [])
    assert await pattern_c.find_pattern_c_all_periods({}, tolerance=0.5) == (None, None, None)
    session.execute.assert_not_called()
