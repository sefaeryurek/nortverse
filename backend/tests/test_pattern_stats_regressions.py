import pytest

from app.analysis.pattern_stats import compute_stats
from app.db.models import Match


def row(**values):
    return Match(**(dict(actual_ft_home=1, actual_ft_away=0,
                        actual_ht_home=0, actual_ht_away=0,
                        actual_h2_home=1, actual_h2_away=0) | values))


def test_handicap_applies_displayed_starting_score():
    stats = compute_stats([row()], "ft")
    assert stats.hnd_a10_x_pct == 100  # 1:0 + 0:1 = 1:1
    assert stats.hnd_a20_2_pct == 100  # 1:0 + 0:2 = 1:2
    assert stats.hnd_h10_1_pct == 100
    assert stats.hnd_h20_1_pct == 100


def test_invalid_archive_scores_do_not_inflate_sample():
    stats = compute_stats([row(), row(actual_ft_home=-1), row(actual_ft_away=31)], "ft")
    assert stats.match_count == 1
    assert stats.result_1_pct == 100


def test_inconsistent_halves_do_not_pollute_full_time_submarkets():
    stats = compute_stats([row(actual_ht_home=2, actual_h2_home=-1)], "ft")
    assert stats.match_count == 1
    assert stats.ht_result_1_pct == 0
    assert stats.h2_result_2_pct == 0
    assert stats.iy_ms_11_pct == 0


def test_second_half_must_reconcile_with_first_half_and_final_score():
    assert compute_stats([row(actual_h2_home=0)], "h2") is None
    stats = compute_stats([row(actual_h2_home=0)], "ft")
    assert stats.h2_result_x_pct == 0


def test_unknown_period_fails_even_for_empty_archive():
    with pytest.raises(ValueError, match="Invalid period"):
        compute_stats([], "typo")
