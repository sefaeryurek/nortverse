"""Skor → sonuç ilkelleri (arşiv istatistikleri ve çözücünün ortak kaynağı)."""

from types import SimpleNamespace

from app.analysis.outcomes import goal_range, handicap_result, margin_bucket, period_scores, result_code


def test_result_and_handicap_convention():
    assert (result_code(2, 1), result_code(1, 1), result_code(0, 2)) == ("1", "x", "2")
    assert handicap_result(0, 1, 2, 0) == "1"   # Hnd (2:0): ev +2 → 2-1
    assert handicap_result(0, 1, 1, 0) == "x"   # Hnd (1:0): 1-1
    assert handicap_result(1, 0, 0, 1) == "x"   # Hnd (0:1): 1-1
    assert handicap_result(2, 0, 0, 2) == "x"   # Hnd (0:2): 2-2


def test_margin_and_goal_buckets():
    assert [margin_bucket(*s) for s in ((1, 0), (3, 1), (5, 0), (2, 2), (0, 1), (1, 3), (0, 4))] == [
        "ev1", "ev2", "ev3p", "ber", "dep1", "dep2", "dep3p"]
    assert [goal_range(n) for n in (0, 1, 2, 3, 4, 5, 6, 9)] == ["01", "01", "23", "23", "45", "45", "6p", "6p"]


def test_period_scores_rejects_inconsistent_halves():
    row = SimpleNamespace(actual_ht_home=1, actual_ht_away=0, actual_h2_home=0, actual_h2_away=0,
                          actual_ft_home=2, actual_ft_away=0)
    assert period_scores(row, "ht") == (1, 0)
    assert period_scores(row, "h2") == (None, None)  # 1 + 0 ≠ 2
