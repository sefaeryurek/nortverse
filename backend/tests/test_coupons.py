"""Kupondaş sonuçlandırma (Sprint 93)."""

from app.analysis.coupons import coupon_status, leg_return


def test_result_and_double_chance():
    assert leg_return("ft", "result", "1", None, 1.8, (0, 0), (2, 1)) == ("hit", 1.8)
    assert leg_return("ft", "result", "X", None, 3.5, (0, 0), (2, 1)) == ("miss", 0.0)
    assert leg_return("ft", "dc", "X2", None, 1.6, None, (1, 1)) == ("hit", 1.6)
    assert leg_return("ft", "dc", "12", None, 1.3, None, (1, 1)) == ("miss", 0.0)
    assert leg_return("ht", "result", "X", None, 2.2, (0, 0), (3, 0)) == ("hit", 2.2)


def test_asian_totals():
    assert leg_return("ft", "ou", "over", 2.5, 1.9, None, (2, 1)) == ("hit", 1.9)
    assert leg_return("ft", "ou", "over", 3.0, 1.9, None, (2, 1)) == ("push", 1.0)
    outcome, factor = leg_return("ft", "ou", "over", 2.75, 2.0, None, (2, 1))
    assert outcome == "half_win" and abs(factor - 1.5) < 1e-9   # yarısı kazanır (2.5), yarısı iade (3.0)
    outcome, factor = leg_return("ht", "ou", "under", 1.25, 1.9, (1, 0), (1, 2))
    assert outcome == "half_win" and abs(factor - 1.45) < 1e-9  # 1.0 iade + 1.5 kazanç
    outcome, factor = leg_return("ht", "ou", "over", 1.25, 1.9, (1, 0), (1, 2))
    assert outcome == "half_loss" and abs(factor - 0.5) < 1e-9


def test_pending_without_score():
    assert leg_return("ft", "result", "1", None, 1.8, (1, 0), None) is None
    assert leg_return("ht", "result", "1", None, 1.8, None, None) is None


def test_coupon_status():
    pending = [{"odds": 1.8, "return_factor": 1.8}, {"odds": 2.0, "return_factor": None}]
    assert coupon_status(pending) == {"total_odds": 3.6, "status": "pending", "return": None}
    lost = [{"odds": 1.8, "return_factor": 0.0}, {"odds": 2.0, "return_factor": None}]
    assert coupon_status(lost)["status"] == "lost"
    won = [{"odds": 1.8, "return_factor": 1.8}, {"odds": 2.0, "return_factor": 1.0}]
    assert coupon_status(won) == {"total_odds": 3.6, "status": "won", "return": 1.8}
