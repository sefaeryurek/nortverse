"""Canlı İY arşiv görünümü + live-arch-v2 kararları: tablo, COND kapısı, tekil karar, defter satırları."""

from types import SimpleNamespace

from app.analysis.live_archive import (
    GENERAL, LIVE_ARCHIVE_RULE_VERSION, ArchiveMatch, build_view, cond_probability, decide,
    ht_filtered_rows, ledger_rows, market_cells, market_decided, rule_params_fingerprint,
)
from app.analysis.live_model import Counts

LEAGUE = "English Premier League"


def _table(ht, finals, league=LEAGUE, global_finals=()):
    """Sahte COND tablosu: ligde `finals` MS skorlarıyla biten, İY'si `ht` olan maçlar."""
    by_score, glob = Counts(), Counts()
    for ft in finals:
        by_score.add(*ft, ht=ht)
        glob.add(*ft, ht=ht)
    for ft in global_finals:
        glob.add(*ft, ht=ht)
    return SimpleNamespace(by_score={league: {ht: by_score}}, global_by_score={ht: glob})


def _cond(table, ht, league=LEAGUE):
    return lambda period, market, sel: cond_probability(table, league, ht, period, market, sel)


def _m(mid, ht, ft):
    return ArchiveMatch(mid, ht[0], ht[1], ft[0], ft[1])


def test_rule_params_fingerprint_is_pinned():
    # Eşik/pazar listesi/kapı değişirse kural sürümü (LIVE_ARCHIVE_RULE_VERSION) artırılmalı.
    assert LIVE_ARCHIVE_RULE_VERSION == "live-arch-v2"
    assert rule_params_fingerprint() == "23cf009029b1"


def test_markets_already_decided_by_half_time_are_hidden():
    assert market_decided("ft", "kg", (1, 1)) is True       # iki taraf da attı
    assert market_decided("ft", "ou_15", (2, 0)) is True    # 2 gol oldu
    assert market_decided("ft", "ou_25", (2, 0)) is False
    assert market_decided("ft", "result", (3, 0)) is False
    assert market_decided("h2", "kg", (1, 1)) is False      # 2. yarı pazarları hiç kesinleşmez
    cells = market_cells([_m("1", (1, 1), (2, 1))], (1, 1))
    assert ("ft", "kg") not in {(c["period"], c["market"]) for c in cells}


def test_cells_use_full_time_and_second_half_scores():
    rows = [_m("1", (0, 1), (1, 1)), _m("2", (0, 1), (0, 2)), _m("3", (0, 1), (1, 3))]
    cells = {(c["period"], c["market"]): c for c in market_cells(rows, (0, 1))}
    assert cells[("ft", "dc")]["selection"] == "X2" and cells[("ft", "dc")]["pct"] == 100.0
    assert cells[("h2", "ou_05")]["selection"] == "over" and cells[("h2", "ou_05")]["pct"] == 100.0
    assert cells[("ft", "result")]["options"] == {"1": 0.0, "X": 33.3, "2": 66.7}


def test_general_counts_shared_match_once_and_small_samples_make_no_decision():
    shared = _m("1", (0, 0), (2, 0))
    rows = {"a1": [shared, _m("2", (0, 0), (1, 0))], "a2": [], "a3": [shared]}
    view = build_view(rows, (0, 0), _cond(_table((0, 0), [(1, 0)] * 40), (0, 0)))
    by = {s["archive"]: s for s in view["sources"]}
    assert by[GENERAL]["n"] == 2                     # ortak maç bir kez sayılır
    assert by["a3"]["risky"] is True and by["a2"]["risky"] is False and by["a2"]["n"] == 0
    assert view["highlights"] == []                  # hiçbir kaynak 5 maça ulaşmıyor → karar yok


def test_decision_requires_cond_gate_and_shows_cond_pct():
    ht = (1, 0)
    archive = {"a1": [_m(str(i), ht, (2, 0)) for i in range(6)], "a2": [], "a3": []}
    # Lig geçmişi: İY 1-0'dan 40 maçın 38'i ev kazanmış → MS 1 ≈ %94, kapıdan geçer
    strong = build_view(archive, ht, _cond(_table(ht, [(2, 0)] * 38 + [(1, 1)] * 2), ht))
    result = next(h for h in strong["highlights"] if h["market"] == "result")
    assert result["selection"] == "1" and result["archive_pct"] == 100.0
    assert result["pct"] == round(100 * 38.5 / 41, 1) and result["cond_n"] == 40
    assert result["cond_level"] == "league" and set(result["sources"]) == {"A1", "Genel"}
    # Lig geçmişi zayıf (%60) → arşiv %100 dese de karar yok
    weak = build_view(archive, ht, _cond(_table(ht, [(2, 0)] * 24 + [(1, 1)] * 16), ht))
    assert "result" not in {h["market"] for h in weak["highlights"]}


def test_weak_markets_never_decide():
    ht = (0, 0)
    archive = {"a1": [_m(str(i), ht, (1, 1)) for i in range(8)], "a2": [], "a3": []}
    view = build_view(archive, ht, _cond(_table(ht, [(1, 1)] * 40), ht))
    markets = {(h["period"], h["market"]) for h in view["highlights"]}
    assert not markets & {("ft", "kg"), ("h2", "kg"), ("h2", "result"), ("h2", "ou_15")}
    assert ("ft", "ou_15") in markets                # 1-1 → Üst 1.5 kararı var


def test_conflict_resolved_by_larger_sample():
    sources = [
        {"archive": "a1", "label": "A1", "n": 6, "cells": [
            {"period": "ft", "market": "ou_25", "selection": "over", "pct": 100.0, "options": {}}]},
        {"archive": "a3", "label": "A3", "n": 20, "cells": [
            {"period": "ft", "market": "ou_25", "selection": "under", "pct": 90.0, "options": {}}]},
    ]
    out = decide(sources, lambda *_: {"pct": 88.0, "n": 50, "level": "league"})
    assert len(out) == 1 and out[0]["selection"] == "under" and out[0]["label"] == "A3"
    assert out[0]["conflict"] is True and out[0]["sources"] == ["A3"]


def test_cond_probability_falls_back_to_all_leagues_then_none():
    ht = (2, 2)
    few = _table(ht, [(3, 2)] * 10, global_finals=[(3, 3)] * 30)
    cond = cond_probability(few, LEAGUE, ht, "ft", "ou_35", "over")
    assert cond["level"] == "global" and cond["n"] == 40 and cond["pct"] == 98.8
    assert cond_probability(_table(ht, [(3, 2)] * 10), LEAGUE, ht, "ft", "ou_35", "over") is None


def test_ht_filtered_rows_keep_only_same_half_time_score():
    blobs = {"b": {"matched_ids": ["1", "2", "3"]}, "c": None, "d": {"matched_ids": ["3"]}}
    results = {"1": (0, 1, 1, 1), "2": (1, 1, 1, 1), "3": (0, 1, 0, 3)}
    rows = ht_filtered_rows(blobs, results, (0, 1))
    assert [r.match_id for r in rows["a1"]] == ["1", "3"] and rows["a2"] == []
    assert rows["a3"][0].actual_h2_away == 2


def test_ledger_rows_one_per_decision():
    ht = (1, 0)
    view = build_view({"a1": [_m(str(i), ht, (2, 0)) for i in range(6)], "a2": [], "a3": []}, ht,
                      _cond(_table(ht, [(2, 0)] * 40), ht))
    rows = ledger_rows(view, {"match_id": "9"})
    assert rows and all(r["rule_version"] == LIVE_ARCHIVE_RULE_VERSION and r["source"] == "live_ht" for r in rows)
    keys = [(r["period"], r["market"]) for r in rows]
    assert len(keys) == len(set(keys))                # pazar başına tek satır (tekil sayım)
    assert {r["confidence_tier"] for r in rows} == {"high"}
    first = rows[0]["details"]
    assert first["cond_n"] == 40 and first["archive_pct"] == 100.0 and "A1" in first["sources"]


def test_historical_hit_lookup_by_market_and_sample_bucket():
    from app.analysis.live_archive import annotate, hit_lookup, n_bucket
    assert [n_bucket(n) for n in (0, 1, 3, 7, 12, 40)] == ["1", "1", "2-4", "5-9", "10-19", "20+"]
    table = {("ft", "dc", "5-9"): (80, 100), ("*", "*", "1"): (58, 100), ("ft", "kg", "1"): (5, 10)}
    assert hit_lookup(table, "ft", "dc", 6) == {"pct": 80.0, "n": 100, "bucket": "5-9", "pooled": False}
    # Pazar kovasında 30'dan az işaret → kovanın tüm pazar ortalaması
    assert hit_lookup(table, "ft", "kg", 1)["pooled"] is True and hit_lookup(table, "ft", "kg", 1)["pct"] == 58.0
    assert hit_lookup(table, "h2", "kg", 25) is None
    out = annotate([{"period": "ft", "market": "dc", "n": 6, "pct": 100.0}], table)
    assert out[0]["historical"]["pct"] == 80.0


def test_archive_freeze_window():
    """Arşiv işaretleri devre arası veya 2. yarının ilk 5 dakikası; sonrası ayıklanmış sonuç verir."""
    from app.api.live_ledger import archive_freeze_allowed
    from app.scraper.fixture_scores import FixtureScore

    def fs(phase, minute):
        return FixtureScore("1", "live", 0, 0, 0, 0, minute=minute, phase=phase)

    assert archive_freeze_allowed(fs("ht", None))
    assert archive_freeze_allowed(fs(None, "HT"))
    assert archive_freeze_allowed(fs("2h", "48"))
    assert not archive_freeze_allowed(fs("2h", "51"))
    assert not archive_freeze_allowed(fs("2h", "90+3"))
    assert not archive_freeze_allowed(fs("2h", None))


def test_late_flag_on_archive_rows():
    view = build_view({"a1": [_m(str(i), (1, 0), (2, 0)) for i in range(6)], "a2": [], "a3": []}, (1, 0),
                      _cond(_table((1, 0), [(2, 0)] * 40), (1, 0)))
    assert view["highlights"]
    assert all(r["details"]["late"] is True for r in ledger_rows(view, {"match_id": "9"}, late=True))
    assert all(r["details"]["late"] is False for r in ledger_rows(view, {"match_id": "9"}))


def test_view_cache_key_changes_with_matched_ids():
    from app.analysis.live_archive import _blobs_digest
    a = _blobs_digest({"b": {"matched_ids": ["1", "2"]}, "c": None})
    assert a == _blobs_digest({"c": None, "b": {"matched_ids": ["1", "2"]}})
    assert a != _blobs_digest({"b": {"matched_ids": ["1", "3"]}, "c": None})
