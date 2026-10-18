"""Canlı İY arşiv görünümü (live-arch-v1): oranlar, öne çıkanlar, riskli işaret, defter satırları."""

from app.analysis.live_archive import (
    GENERAL, LIVE_ARCHIVE_RULE_VERSION, ArchiveMatch, build_view, ht_filtered_rows, ledger_rows,
    market_cells, market_decided, rule_params_fingerprint,
)


def _m(mid, ht, ft):
    return ArchiveMatch(mid, ht[0], ht[1], ft[0], ft[1])


def test_rule_params_fingerprint_is_pinned():
    # Eşik/pazar listesi değişirse kural sürümü (LIVE_ARCHIVE_RULE_VERSION) artırılmalı.
    assert LIVE_ARCHIVE_RULE_VERSION == "live-arch-v1"
    assert rule_params_fingerprint() == "aef5af6267c5"


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


def test_view_highlights_risky_and_general_without_duplicates():
    shared = _m("1", (0, 0), (2, 0))
    rows = {"a1": [shared, _m("2", (0, 0), (1, 0))], "a2": [], "a3": [shared]}
    view = build_view(rows, (0, 0))
    by = {s["archive"]: s for s in view["sources"]}
    assert by[GENERAL]["n"] == 2                     # ortak maç bir kez sayılır
    assert by["a3"]["risky"] is True and by["a2"]["risky"] is False and by["a2"]["n"] == 0
    assert all(h["pct"] >= 85 for h in view["highlights"])
    assert view["highlights"][0]["risky"] is True   # 5 maçtan az: hepsi riskli ama gösterilir
    assert {"a1", "a3", GENERAL} == {h["archive"] for h in view["highlights"]}


def test_ht_filtered_rows_keep_only_same_half_time_score():
    blobs = {"b": {"matched_ids": ["1", "2", "3"]}, "c": None, "d": {"matched_ids": ["3"]}}
    results = {"1": (0, 1, 1, 1), "2": (1, 1, 1, 1), "3": (0, 1, 0, 3)}
    rows = ht_filtered_rows(blobs, results, (0, 1))
    assert [r.match_id for r in rows["a1"]] == ["1", "3"] and rows["a2"] == []
    assert rows["a3"][0].actual_h2_away == 2


def test_ledger_rows_one_per_highlight():
    view = build_view({"a1": [_m(str(i), (1, 0), (2, 0)) for i in range(6)], "a2": [], "a3": []}, (1, 0))
    rows = ledger_rows(view, {"match_id": "9"})
    assert rows and all(r["rule_version"] == LIVE_ARCHIVE_RULE_VERSION and r["source"] == "live_ht" for r in rows)
    general = [r for r in rows if r["archive"] is None]
    assert general and all(r["details"]["label"] == "Genel" for r in general)
    assert {r["confidence_tier"] for r in rows} == {"high"}   # 6 maç → riskli değil
