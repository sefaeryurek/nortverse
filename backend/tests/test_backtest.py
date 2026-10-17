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
