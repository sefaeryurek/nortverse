"""Gölgedeki yeni ligler (Sprint 92): ad eşlemesi ve ana liglerin oranlarının değişmemesi."""

from datetime import datetime, timezone

from app.analysis.league_filter import canonical_league_name, is_main_league, is_shadow_league, is_tracked_league
from app.analysis.league_priors import book_from_counts
from app.analysis.live_model import CondTable

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)


def test_bulletin_and_short_codes_map_to_one_name():
    # Bülten tam adı ile H2H kısa kodu farklı kanonik ada giderse lig süzgeci hiç eşleşme bulamaz
    assert canonical_league_name("German Bundesliga 2") == canonical_league_name("GER D2")
    assert canonical_league_name("Liga Portugal 1") == canonical_league_name("POR D1")
    assert canonical_league_name("England Championship") == canonical_league_name("ENG LCH")
    for name in ("Scottish Premiership", "SCO PR", "Belgian Pro League", "BEL D1"):
        assert is_shadow_league(name) and is_tracked_league(name) and not is_main_league(name)
    assert not is_shadow_league("Austrian Bundesliga") and not is_tracked_league("Liga Portugal 2")


def test_cond_all_leagues_fallback_uses_main_leagues_only():
    table = CondTable(cutoff=NOW, prior_from=NOW)
    table.add("English Premier League", 1, 0, 2, 0, NOW)
    table.add("English Championship", 1, 0, 1, 1, NOW)
    assert table.global_by_score[(1, 0)].n == 1          # gölge lig "tüm ligler" havuzuna girmez
    assert table.by_score["English Championship"][(1, 0)].n == 1   # kendi lig geçmişi yine kurulur


def test_prior_overall_uses_main_leagues_only():
    rows = [("English Premier League", 50, 25, 25, 50, 50), ("Scottish Premiership", 0, 0, 100, 0, 0)]
    book = book_from_counts(NOW, rows)
    assert abs(book.overall.result["1"] - book.get("English Premier League").result["1"]) < 1e-9
    assert book.get("Scottish Premiership").result["2"] > 0.9
