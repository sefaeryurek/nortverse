"""Pazar kataloğu + sonuç çözücü testleri."""

import re
from pathlib import Path

import pytest

from app.analysis.market_catalog import MARKETS, SUMMARY_MARKET_KEYS, get_market
from app.analysis.market_resolver import resolve
from app.analysis.pattern_stats import PatternResult

_CONFIDENCE_TS = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "confidence.ts"

# Seçimleri birbirini dışlayan ve her skoru kapsayan pazarlar: her skorda tam 1 isabet.
# dc/ht_dc çakışır (2 isabet); iki_yari_15 karışık yarılarda hiçbiri tutmaz.
_PARTITION_MARKETS = [m.key for m in MARKETS if m.key not in {"dc", "ht_dc", "iki_yari_15"}]
_GRID = [((hh, ha), (fh, fa)) for fh in range(5) for fa in range(5)
         for hh in range(fh + 1) for ha in range(fa + 1)]


def test_every_catalog_field_exists_in_pattern_result():
    fields = set(PatternResult.model_fields)
    for market in MARKETS:
        for field, _ in market.fields:
            assert field in fields, f"{market.key}: {field}"


@pytest.mark.skipif(not _CONFIDENCE_TS.exists(), reason="frontend kaynağı yok")
def test_catalog_matches_frontend_markets():
    ts_fields = set(re.findall(r'field:\s*"([a-z0-9_]+)"', _CONFIDENCE_TS.read_text(encoding="utf-8")))
    py_fields = {field for market in MARKETS for field, _ in market.fields}
    assert py_fields == ts_fields
    ts_summary = re.search(r"SUMMARY_MARKET_KEYS = \[(.*?)\]", _CONFIDENCE_TS.read_text(encoding="utf-8"), re.S)
    assert tuple(re.findall(r'"([a-z0-9_]+)"', ts_summary.group(1))) == SUMMARY_MARKET_KEYS


@pytest.mark.parametrize("market_key", _PARTITION_MARKETS)
@pytest.mark.parametrize("period", ["ht", "h2", "ft"])
def test_partition_markets_have_exactly_one_hit(market_key, period):
    market = get_market(market_key)
    if not market.active_in(period):
        return
    for ht, ft in _GRID:
        hits = [code for _, code in market.fields if resolve(period, market_key, code, ht, ft) == "hit"]
        assert len(hits) == 1, f"{market_key}/{period} {ht}->{ft}: {hits}"


@pytest.mark.parametrize("period", ["ht", "h2", "ft"])
def test_double_chance_has_exactly_two_hits(period):
    for ht, ft in _GRID:
        hits = [code for code in ("1X", "X2", "12") if resolve(period, "dc", code, ht, ft) == "hit"]
        assert len(hits) == 2


@pytest.mark.parametrize("market, selection, ht, ft, expected", [
    ("result", "1", (0, 0), (2, 1), "hit"),
    ("result", "X", (0, 0), (2, 1), "miss"),
    ("hnd_h20", "1", (0, 0), (0, 1), "hit"),     # (2:0): ev +2 → 2-1
    ("hnd_a10", "X", (0, 0), (1, 0), "hit"),     # (0:1): dep +1 → 1-1
    ("hnd_a20", "2", (0, 0), (1, 0), "hit"),     # (0:2): dep +2 → 1-2
    ("fark", "h2", (1, 0), (3, 1), "hit"),
    ("ou_25", "over", (1, 1), (2, 1), "hit"),
    ("kg", "no", (1, 0), (2, 0), "hit"),
    ("iy_ms", "X/1", (0, 0), (1, 0), "hit"),
    ("ms_25_combo", "2_under", (0, 0), (0, 1), "hit"),
    ("encok_yari", "2h", (0, 0), (2, 1), "hit"),
])
def test_known_outcomes(market, selection, ht, ft, expected):
    assert resolve("ft", market, selection, ht, ft) == expected


def test_both_halves_market_mixed_case_has_no_hit():
    assert resolve("ft", "iki_yari_15", "under", (0, 0), (0, 2)) == "miss"
    assert resolve("ft", "iki_yari_15", "over", (0, 0), (0, 2)) == "miss"
    assert resolve("ft", "iki_yari_15", "over", (1, 1), (2, 2)) == "hit"


def test_second_half_uses_goal_difference_of_halves():
    assert resolve("h2", "result", "2", (2, 0), (2, 1)) == "hit"


def test_unresolvable_without_scores():
    assert resolve("ft", "result", "1", None, None) is None
    assert resolve("ht", "result", "1", None, (1, 0)) is None
    assert resolve("ft", "iy_ms", "1/1", None, (1, 0)) is None


def test_inactive_period_is_unresolvable():
    assert resolve("ht", "ou_25", "over", (1, 1), (2, 2)) is None


def test_unknown_selection_raises():
    with pytest.raises(ValueError):
        resolve("ft", "result", "Z", (0, 0), (1, 0))
