"""Performans paneli hesapları."""

from datetime import datetime, timezone

import pytest

from app.analysis.performance import calibration_buckets, dedupe_decisions, group_summaries, summarize
from app.api.routes_performance import _merge_pick

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


def test_agreement_group_key():
    from datetime import datetime, timezone
    from app.analysis.performance import group_summaries
    base = {"period": "ft", "market": "result", "outcome": "hit", "prob_shown_bp": 5000,
            "kickoff_time": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    keys = {g["key"] for g in group_summaries([{**base, "agreement": 3}, {**base, "agreement": None}], "agreement")}
    assert keys == {"3", "-"}


def _arch(archive, n, prob_bp, outcome="hit", selection="over", tier="medium", match_id="1"):
    return {"match_id": match_id, "rule_version": "live-arch-v1", "period": "ft", "market": "ou_15",
            "selection": selection, "archive": archive, "sample_n": n, "prob_shown_bp": prob_bp,
            "confidence_tier": tier, "outcome": outcome}


def test_same_selection_from_several_archives_counts_once():
    """A1/A2/A3/Genel aynı seçimi işaret ederse tek karar — eskiden 4 isabet sayılıyordu."""
    rows = [_arch("a1", 3, 10000, tier="insufficient"), _arch("a2", 12, 9000),
            _arch("a3", 40, 8800), _arch(None, 60, 8700), _arch("a1", 4, 9000, match_id="2", outcome="miss")]
    unique = dedupe_decisions(rows)
    assert len(unique) == 2
    first = next(r for r in unique if r["match_id"] == "1")
    assert first["sample_n"] == 60 and first["prob_shown_bp"] == 8700   # en büyük örneklem temsil eder
    assert sorted(first["sources"]) == ["a1", "a2", "a3", "genel"]
    assert summarize(unique)["resolved"] == 2


def test_conflicting_selections_stay_separate_decisions():
    rows = [_arch("a1", 10, 9000, selection="over"), _arch("a2", 10, 9000, selection="under", outcome="miss")]
    assert len(dedupe_decisions(rows)) == 2


def test_rows_without_match_id_are_not_deduped():
    rows = [_row("hit"), _row("hit")]
    assert dedupe_decisions(rows) == rows


def test_live_match_picks_merge_by_selection():
    picks: list[dict] = []
    base = {"period": "ft", "market": "ou_15", "selection": "over", "outcome": "hit"}
    _merge_pick(picks, {**base, "archive": "a1", "label": "A1", "pct": 100.0, "n": 2, "risky": True})
    _merge_pick(picks, {**base, "archive": "genel", "label": "GENEL", "pct": 88.0, "n": 50, "risky": False})
    _merge_pick(picks, {**base, "selection": "under", "archive": "a3", "label": "A3", "pct": 90.0, "n": 9, "risky": False})
    assert len(picks) == 2
    assert picks[0]["labels"] == ["A1", "GENEL"]
    assert picks[0]["n"] == 50 and picks[0]["pct"] == 88.0 and picks[0]["risky"] is False


def test_verdict_protocol():
    from app.analysis.stats_utils import verdict
    assert verdict(60, 80, 0.7) == "collecting"               # 100 tekil karar yok → hüküm yok
    assert verdict(66, 100, 0.92) == "below"                  # %66 gerçek, %92 gösterilen → askı
    assert verdict(92, 100, 0.90) == "on_track"
    assert verdict(140, 150, 0.80) == "above"
    s = summarize([_row("hit", 9000)] * 90 + [_row("miss", 9000)] * 10)
    assert s["verdict"] == "on_track" and s["expected_hits"] == 90.0


def test_live_match_picks_do_not_merge_across_rule_versions():
    picks: list[dict] = []
    base = {"period": "ft", "market": "dc", "selection": "1X", "outcome": "hit", "pct": 90.0, "n": 40,
            "risky": False, "archive": "genel", "label": "GENEL"}
    _merge_pick(picks, {**base, "rule_version": "live-arch-v1"})
    _merge_pick(picks, {**base, "rule_version": "live-arch-v2"})
    assert len(picks) == 2


def test_archive_breakdown_counts_each_supporting_archive():
    from app.analysis.performance import expand_by_archive
    row = {"archive": None, "outcome": "hit", "details": {"sources": ["A3", "Genel"]}}
    plain = {"archive": "a1", "outcome": "miss", "details": {}}
    assert [r["archive"] for r in expand_by_archive([row, plain])] == ["a3", "genel", "a1"]


def test_backtest_run_current_flag_uses_its_own_rule_version():
    from app.analysis import live_archive, live_poisson, prematch_v4, prematch_v5
    from app.api.routes_performance import _is_current
    assert _is_current(prematch_v5.V5_RULE_VERSION, {"params_fingerprint": prematch_v5.rule_params_fingerprint()})
    assert _is_current(live_poisson.LIVE_POISSON_RULE_VERSION,
                       {"params_fingerprint": live_poisson.rule_params_fingerprint()})
    assert _is_current(live_archive.LIVE_ARCHIVE_RULE_VERSION,
                       {"params_fingerprint": live_archive.rule_params_fingerprint()})
    assert not _is_current(prematch_v5.V5_RULE_VERSION, {"params_fingerprint": prematch_v4.rule_params_fingerprint()})
    assert not _is_current("live-arch-v1", {"params_fingerprint": live_archive.rule_params_fingerprint()})


def test_summary_defaults_to_on_screen_rule_version():
    from app.api.routes_performance import on_screen_rule_version
    assert on_screen_rule_version("live_ht") == "live-poisson-v1.1"
    assert on_screen_rule_version("top_pick") == "ft-display-v5"


def test_coverage_summary_counts_only_scope_and_lists_missed():
    """Sprint 94 C4: devre arasına gelen izlenen maçların kaçı canlı kaydedildi."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from app.api.routes_performance import coverage_summary

    k = datetime(2026, 10, 28, 17, tzinfo=timezone.utc)
    row = lambda mid, league, frozen: SimpleNamespace(match_id=mid, home_team=f"H{mid}", away_team=f"A{mid}",  # noqa: E731
                                                      league_name=league, kickoff_time=k, frozen=frozen)
    rows = [row("1", "English Premier League", True), row("2", "Italy Serie A", False),
            row("3", "English Championship", True), row("4", "Peru Liga 1", False)]
    main = coverage_summary(rows, "main")
    assert (main["reached_ht"], main["frozen"], main["pct"]) == (2, 1, 50.0)
    assert [m["match_id"] for m in main["missed"]] == ["2"]
    shadow = coverage_summary(rows, "shadow")
    assert (shadow["reached_ht"], shadow["frozen"]) == (1, 1)
    assert coverage_summary([], "main")["pct"] is None
