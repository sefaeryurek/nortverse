"""Performans paneli hesapları."""

from datetime import datetime, timezone

import pytest

from app.analysis.performance import calibration_buckets, group_summaries, summarize

KO = datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)


def _row(outcome, prob_bp=6000, baseline=None, **kw):
    base = dict(outcome=outcome, prob_shown_bp=prob_bp, baseline_outcome=baseline, market="result",
                selection="1", period="ft", confidence_tier="high", league_name="L", kickoff_time=KO,
                archive=None, informational=False)
    base.update(kw)
    return base


def test_summary_counts_and_rates():
    rows = [_row("hit"), _row("hit"), _row("miss"), _row(None), _row("void")]
    s = summarize(rows)
    assert (s["total"], s["resolved"], s["pending"], s["void"], s["hits"]) == (5, 3, 1, 1, 2)
    assert s["hit_pct"] == pytest.approx(66.7)
    assert s["avg_prob_pct"] == 60.0
    assert s["calibration_gap"] == pytest.approx(-6.7)
    assert s["stage"] == "cok_erken"
    assert s["ci_low"] < s["hit_pct"] < s["ci_high"]


def test_brier_for_selected_outcome():
    s = summarize([_row("hit", 8000), _row("miss", 8000)])
    assert s["brier"] == pytest.approx((0.04 + 0.64) / 2)


def test_lift_compares_model_and_baseline_on_same_matches():
    rows = [_row("hit", baseline="miss"), _row("hit", baseline="hit"), _row("miss", baseline="miss"),
            _row("hit")]  # tabansız satır farka girmez
    s = summarize(rows)
    assert s["baseline_resolved"] == 3
    assert s["baseline_hit_pct"] == pytest.approx(33.3)
    assert s["lift_pct"] == pytest.approx(33.3)


def test_empty_summary_has_no_rates():
    s = summarize([])
    assert s["hit_pct"] is None and s["brier"] is None and s["stage"] == "cok_erken"


def test_group_by_tier_sorted_by_volume():
    rows = [_row("hit", confidence_tier="low")] + [_row("hit"), _row("miss")]
    groups = group_summaries(rows, "tier")
    assert [g["key"] for g in groups] == ["high", "low"]


def test_group_by_day_uses_istanbul_date():
    late_utc = datetime(2026, 10, 17, 22, 30, tzinfo=timezone.utc)  # İstanbul 18 Ekim 01:30
    groups = group_summaries([_row("hit", kickoff_time=late_utc)], "day")
    assert groups[0]["key"] == "2026-10-18"


def test_calibration_buckets():
    rows = [_row("hit", 7200), _row("miss", 7800), _row("hit", 9500), _row(None, 5000)]
    buckets = calibration_buckets(rows)
    assert [(b["lower"], b["n"], b["hit_pct"]) for b in buckets] == [(70, 2, 50.0), (90, 1, 100.0)]


def test_period_market_group_key():
    from datetime import datetime, timezone
    from app.analysis.performance import group_summaries
    rows = [{"period": "ht", "market": "kg", "outcome": "hit", "prob_shown_bp": 7000,
             "kickoff_time": datetime(2026, 1, 1, tzinfo=timezone.utc)}]
    assert group_summaries(rows, "period_market")[0]["key"] == "ht:kg"
