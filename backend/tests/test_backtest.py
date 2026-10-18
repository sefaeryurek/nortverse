"""Backtest yardımcıları: kayan prior penceresi ve çok sınıflı Brier."""

from datetime import datetime, timedelta, timezone

import pytest

from app.analysis.backtest import IncrementalCondTable, multiclass_brier

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
LEAGUE = "English Premier League"


def test_incremental_prior_slides_and_cond_keeps_history():
    table = IncrementalCondTable(cutoff=T0, prior_from=T0)
    table.add(LEAGUE, 0, 0, 1, 0, T0)                       # eski: ev kazandı
    table.add(LEAGUE, 0, 0, 0, 1, T0 + timedelta(days=400))  # yeni: dep kazandı
    assert table.prior[LEAGUE].n == 2
    table.advance_prior(T0 + timedelta(days=100))
    assert (table.prior[LEAGUE].n1, table.prior[LEAGUE].n2) == (0, 1)
    assert table.by_score[LEAGUE][(0, 0)].n == 2  # COND geçmişi silinmez


def test_multiclass_brier():
    probs = {"1": 0.6, "X": 0.3, "2": 0.1}
    assert multiclass_brier(probs, (2, 0)) == pytest.approx(0.16 + 0.09 + 0.01)
    assert multiclass_brier(probs, (1, 1)) == pytest.approx(0.36 + 0.49 + 0.01)


def _blob(mc=40, r1=70.0, rx=15.0, r2=15.0):
    return {"match_count": mc, "result_1_pct": r1, "result_x_pct": rx, "result_2_pct": r2,
            "ust_25_pct": 60.0, "kg_var_pct": 40.0}


def _match(**kw):
    from types import SimpleNamespace
    base = {f"pattern_{p}_{f}": None for p in ("ht", "h2", "ft") for f in "bcd"}
    base.update(match_id="1", league_name="ENG PR", kickoff_time=T0,
                actual_ht_home=1, actual_ht_away=0, actual_ft_home=2, actual_ft_away=1)
    base.update(kw)
    return SimpleNamespace(**base)


def test_prematch_rows_resolve_top_pick_with_real_result():
    from app.analysis.backtest import prematch_rows
    table = IncrementalCondTable(cutoff=T0, prior_from=T0 - timedelta(days=1000))
    for _ in range(40):
        table.add(LEAGUE, 0, 0, 1, 1, T0 - timedelta(days=30))  # lig ortalaması: hep beraberlik
        table.add(LEAGUE, 0, 0, 0, 1, T0 - timedelta(days=30))
    match = _match(pattern_ft_b=_blob(), pattern_ft_c=_blob())
    rows = prematch_rows(table, match, T0, run_id=7, strategy="top_pick")
    result = [r for r in rows if r["market"] == "result"]
    assert len(result) == 1 and result[0]["selection"] == "1" and result[0]["outcome"] == "hit"
    assert result[0]["league_name"] == LEAGUE and result[0]["run_id"] == 7
    assert {r["source"] for r in rows} == {"top_pick"}
    assert all(r["informational"] for r in rows if r["market"] != "result")


def test_prematch_rows_market_summary_only_and_ht_resolution():
    from app.analysis.backtest import prematch_rows
    table = IncrementalCondTable(cutoff=T0, prior_from=T0)
    match = _match(pattern_ht_b=_blob(r1=20.0, rx=60.0, r2=20.0))
    rows = prematch_rows(table, match, T0, run_id=1, strategy="market_summary")
    ht_result = next(r for r in rows if r["period"] == "ht" and r["market"] == "result")
    assert ht_result["selection"] == "X" and ht_result["outcome"] == "miss"  # İY 1-0
    assert {r["source"] for r in rows} == {"market_summary"}
