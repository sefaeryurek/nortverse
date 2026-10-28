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


# Sprint 94 J1: ajanın 12 durumluk karşılaştırması (6 uyuşmazlık vardı) kalıcı test oldu
import pytest  # noqa: E402


@pytest.mark.parametrize("factors,status,ret", [
    ([1.9, 1.0], "won", 1.9),
    ([0.5], "partial_loss", 0.5),
    ([0.5, 1.0], "partial_loss", 0.5),
    ([1.45, 0.5], "partial_loss", 0.725),
    ([1.45], "won", 1.45),
    ([1.0, 1.0], "refund", 1.0),
    ([None, 0.0], "lost", 0.0),
    ([None, 1.9], "pending", None),
    ([1.9, 1.9], "won", 3.61),
    ([0.5, 0.5], "partial_loss", 0.25),
    ([1.005, 0.5], "partial_loss", 0.502),
    ([1.0000000001], "refund", 1.0),
])
def test_coupon_status_partial_loss(factors, status, ret):
    out = coupon_status([{"odds": 2.0, "return_factor": f} for f in factors])
    assert out["status"] == status and out["return"] == ret


def test_ht_leg_void_when_full_time_known_but_no_ht_for_24h():
    from datetime import datetime, timedelta, timezone

    from app.analysis.coupons import leg_void_reason

    now = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
    kick = now - timedelta(hours=25)
    assert leg_void_reason(deleted=False, status=None, has_score=False, kickoff=kick, now=now,
                           ft_known=True, period="ht") == "no_ht_24h"
    assert leg_void_reason(deleted=False, status=None, has_score=False, kickoff=kick, now=now,
                           ft_known=False, period="ht") is None


# ─── Sprint 94 J8: açık kuponların canlı durumu ─────────────────────────────────────────────────

def _board(status="live", home=1, away=0, ht=(None, None), phase="1h", minute="30"):
    from app.scraper.fixture_scores import FixtureScore

    return FixtureScore(match_id="1", status=status, home=home, away=away, ht_home=ht[0], ht_away=ht[1],
                        minute=minute, phase=phase)


def test_live_leg_state_ft_and_ht():
    from app.analysis.coupons import live_leg_state

    s = live_leg_state("ft", "result", "1", None, 2.0, _board())
    assert s["state"] == "winning" and s["score"] == "1-0" and not s["period_over"]
    assert live_leg_state("ft", "ou", "over", 2.5, 1.9, _board())["state"] == "losing"
    assert live_leg_state("ft", "ou", "under", 1.0, 1.9, _board())["state"] == "level"  # tam çizgide şu an iade
    # İY bacağı: 2. yarıda panonun İY skoru esas, sonuç kesin
    s = live_leg_state("ht", "result", "X", None, 2.1, _board(home=2, away=1, ht=(1, 1), phase="2h", minute="60"))
    assert s["state"] == "winning" and s["period_score"] == "1-1" and s["period_over"]
    # Başlamamış / ertelenmiş / uzatmalı maç sonucu yok
    assert live_leg_state("ft", "result", "1", None, 2.0, _board(status="postponed")) is None
    assert live_leg_state("ft", "result", "1", None, 2.0, _board(status="finished_extra")) is None
    assert live_leg_state("ft", "result", "1", None, 2.0, None) is None


def test_live_summary():
    from app.analysis.coupons import live_summary

    win, lose, level = ({"live": {"state": s}} for s in ("winning", "losing", "level"))
    settled = {"return_factor": 1.8, "live": None}
    assert live_summary([settled, win, level]) == "winning"
    assert live_summary([win, lose]) == "losing"
    assert live_summary([win, {"live": None}]) is None  # bir bacak henüz başlamadı
    assert live_summary([settled]) is None


# ─── Sprint 94 J9: kullanıcı karnesi ────────────────────────────────────────────────────────────

def test_user_stats_profit_roi_and_leg_hits():
    from app.analysis.coupons import user_stats

    def coupon(user, factors, outcomes):
        legs = [{"odds": 2.0, "return_factor": f, "outcome": o} for f, o in zip(factors, outcomes)]
        return {"username": user, "legs": legs, **coupon_status(legs)}

    rows = [
        coupon("ali", [2.0, 2.0], ["hit", "hit"]),          # kazandı 4,0 → +3
        coupon("ali", [0.0, None], ["miss", None]),         # kaybetti → −1
        coupon("ali", [None], [None]),                      # bekliyor
        coupon("veli", [1.0], ["void"]),                    # iade → 0
        coupon("veli", [1.5], ["half_win"]),                # kazandı 1,5 → +0,5
    ]
    ali, veli = user_stats(rows)
    assert ali["username"] == "ali" and ali["coupons"] == 3 and ali["settled"] == 2 and ali["pending"] == 1
    assert ali["profit"] == 2.0 and ali["roi_pct"] == 100.0
    assert ali["leg_hit_pct"] == 66.7 and ali["legs_decided"] == 3
    assert ali["best_won_odds"] == 4.0 and ali["avg_odds"] == 3.33  # (4 + 4 + 2) / 3
    assert veli["profit"] == 0.5 and veli["refund"] == 1 and veli["won"] == 1
    assert veli["leg_hit_pct"] == 100.0 and veli["legs_decided"] == 1  # iade bacak isabete sayılmaz


def test_user_stats_without_settled_coupons():
    from app.analysis.coupons import user_stats

    legs = [{"odds": 1.8, "return_factor": None, "outcome": None}]
    (row,) = user_stats([{"username": "a", "legs": legs, **coupon_status(legs)}])
    assert row["roi_pct"] is None and row["leg_hit_pct"] is None and row["profit"] == 0
