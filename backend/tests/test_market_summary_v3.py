"""Ana Pazar Özeti v3 gölge (Sprint 94 H1)."""

import math

from app.analysis import market_summary_v3 as v3


def _grid(lh, la, n=10):
    ph = [math.exp(-lh) * lh ** k / math.factorial(k) for k in range(n + 1)]
    pa = [math.exp(-la) * la ** k / math.factorial(k) for k in range(n + 1)]
    return [(x, y, ph[x] * pa[y]) for x in range(n + 1) for y in range(n + 1)]


def test_probabilities_sum_to_one_for_exclusive_markets():
    probs = v3.market_probabilities(_grid(1.6, 1.1))
    for key in ("result", "ou_25", "kg", "fark", "ms_25_combo", "hnd_h10"):
        assert abs(sum(probs[key].values()) - 1) < 1e-6
    assert "iy_ms" not in probs  # İY skoru gerektiren pazar ızgaradan çözülemez


def test_rows_pick_model_argmax_and_keep_archive_frequency():
    patterns = {"pattern_ft_b": {"match_count": 40, "result_1_pct": 55.0}, "pattern_ft_c": None}
    common = {"match_id": "1", "league_name": "L", "kickoff_time": None, "as_of": None}
    rows = {r["market"]: r for r in v3.ledger_rows(_grid(2.0, 0.6), patterns, common)}
    result = rows["result"]
    assert result["selection"] == "1" and result["rule_version"] == "market-summary-v3"
    assert result["details"]["shadow"] is True and result["details"]["archive_pct"] == {"a1": 55.0}
    assert 5000 < result["prob_shown_bp"] < 10000


def test_no_grid_no_rows():
    assert v3.ledger_rows(None, {}, {}) == []
