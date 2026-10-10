"""Temporal decay weight hesaplama testleri."""

import math
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

from app.analysis.pattern_b import _temporal_weights


def _row(kickoff_time):
    return SimpleNamespace(kickoff_time=kickoff_time)


def test_zero_half_life_returns_equal_weights():
    as_of = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = [_row(datetime(2020, 1, 1, tzinfo=timezone.utc)) for _ in range(5)]
    weights = _temporal_weights(rows, as_of, half_life_years=0)
    assert all(w == 1.0 for w in weights)


def test_recent_match_gets_weight_near_one():
    as_of = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = [_row(datetime(2026, 9, 1, tzinfo=timezone.utc))]
    weights = _temporal_weights(rows, as_of, half_life_years=3.0)
    assert weights[0] > 0.95


def test_three_year_old_match_gets_weight_near_half():
    as_of = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = [_row(datetime(2023, 10, 1, tzinfo=timezone.utc))]
    weights = _temporal_weights(rows, as_of, half_life_years=3.0)
    assert abs(weights[0] - 0.5) < 0.02


def test_six_year_old_match_gets_weight_near_quarter():
    as_of = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = [_row(datetime(2020, 10, 1, tzinfo=timezone.utc))]
    weights = _temporal_weights(rows, as_of, half_life_years=3.0)
    assert abs(weights[0] - 0.25) < 0.02


def test_none_kickoff_time_gets_weight_one():
    as_of = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = [_row(None)]
    weights = _temporal_weights(rows, as_of, half_life_years=3.0)
    assert weights[0] == 1.0


def test_naive_kickoff_time_handled():
    as_of = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = [_row(datetime(2023, 10, 1))]
    weights = _temporal_weights(rows, as_of, half_life_years=3.0)
    assert abs(weights[0] - 0.5) < 0.02


def test_ordering_recent_to_old():
    as_of = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = [
        _row(datetime(2026, 9, 1, tzinfo=timezone.utc)),
        _row(datetime(2024, 10, 1, tzinfo=timezone.utc)),
        _row(datetime(2020, 10, 1, tzinfo=timezone.utc)),
    ]
    weights = _temporal_weights(rows, as_of, half_life_years=3.0)
    assert weights[0] > weights[1] > weights[2]
