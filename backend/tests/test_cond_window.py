"""COND tablosu zaman penceresi (Sprint 94 C1, K9)."""

from datetime import datetime, timedelta, timezone

from app.analysis.backtest import IncrementalCondTable
from app.analysis.live_model import COND_WINDOW_YEARS, CondTable, window_start

NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)
LEAGUE = "English Premier League"


def _table(window_years):
    return CondTable(cutoff=NOW, prior_from=NOW - timedelta(days=1095), window_from=window_start(NOW, window_years))


def test_old_rows_outside_window_do_not_change_cond():
    old = NOW - timedelta(days=365 * 15)
    recent = NOW - timedelta(days=100)
    full, windowed = _table(None), _table(COND_WINDOW_YEARS)
    for table in (full, windowed):
        table.add(LEAGUE, 1, 0, 2, 0, recent)
        table.add(LEAGUE, 1, 0, 1, 1, old)
    assert full.by_score[LEAGUE][(1, 0)].n == 2
    assert windowed.by_score[LEAGUE][(1, 0)].n == 1     # 15 yıllık arşiv eklemesi pencereli tabloyu değiştirmez
    assert windowed.prior[LEAGUE].n == 1                 # lig prior'u ayrıca son 3 sezon


def test_two_builds_with_same_as_of_are_identical():
    rows = [(LEAGUE, 0, 0, 1, 0, NOW - timedelta(days=d)) for d in (10, 400, 5000)]
    a, b = _table(COND_WINDOW_YEARS), _table(COND_WINDOW_YEARS)
    for r in rows:
        a.add(*r)
    for r in reversed(rows):
        b.add(*r)
    assert a.by_score == b.by_score and a.by_diff == b.by_diff


def test_incremental_window_drops_expired_rows():
    table = IncrementalCondTable(cutoff=NOW, prior_from=NOW, window_years=1)
    table.add(LEAGUE, 1, 0, 2, 0, NOW - timedelta(days=500))
    table.add(LEAGUE, 1, 0, 1, 1, NOW - timedelta(days=10))
    table.advance_window(NOW)
    counts = table.by_score[LEAGUE][(1, 0)]
    assert counts.n == 1 and counts.nx == 1 and counts.pairs[(1, 0, 2, 0)] == 0


def test_incremental_table_reference_pool_is_main_leagues_only():
    """Backtest tablosu canlı tabloyla aynı: 'tüm ligler' yedeğine gölge ligler girmez."""
    table = IncrementalCondTable(cutoff=NOW, prior_from=NOW)
    table.add("Scottish Premiership", 0, 0, 0, 0, NOW - timedelta(days=5))
    table.add(LEAGUE, 0, 0, 1, 0, NOW - timedelta(days=5))
    assert table.global_by_score[(0, 0)].n == 1
