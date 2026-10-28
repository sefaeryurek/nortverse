"""live-cond-filter-v1 (Sprint 94 Faz O, gölge): lig geçmişi ≥%85 ama takım gücü modeli <%85."""

from app.analysis import live_cond_filter as lcf

PRED = {
    "lambda_2h": {"home": 0.6, "away": 0.5}, "lambda_ft": {"home": 1.4, "away": 1.1},
    "cells": [
        {"period": "ft", "market": "ou_35", "selection": "under", "pct": 82.0, "options": {"under": 82.0, "over": 18.0}},
        {"period": "ft", "market": "dc", "selection": "1X", "pct": 91.0, "options": {"1X": 91.0, "12": 70.0, "X2": 40.0}},
        {"period": "ft", "market": "ou_25", "selection": "under", "pct": 60.0, "options": {"under": 60.0, "over": 40.0}},
    ],
}


def _cond(table):
    return lambda period, market, sel: table.get((period, market, sel))


def test_warns_only_when_history_high_and_model_low():
    cond = _cond({
        ("ft", "ou_35", "under"): {"pct": 90.0, "n": 120},   # model 82 → uyarı
        ("ft", "dc", "1X"): {"pct": 95.0, "n": 200},         # model 91 → model de yüksek, uyarı yok
        ("ft", "dc", "12"): {"pct": 86.0, "n": 10},          # az maç → yok
        ("ft", "ou_25", "under"): {"pct": 88.0, "n": 50},    # dışlanan pazar (DECISION_PARAMS) → yok
    })
    out = lcf.warnings(PRED, cond)
    assert [(w["market"], w["selection"], w["cond_pct"], w["model_pct"]) for w in out] == [("ou_35", "under", 90.0, 82.0)]


def test_ledger_rows_show_cond_probability_as_shadow():
    picks = [{"period": "ft", "market": "ou_35", "selection": "under", "cond_pct": 90.0, "cond_n": 120, "model_pct": 82.0}]
    (row,) = lcf.ledger_rows(PRED, picks, {"match_id": "1"}, late=False)
    assert row["rule_version"] == "live-cond-filter-v1" and row["prob_shown_bp"] == 9000
    assert row["details"]["shadow"] is True and row["details"]["model_pct"] == 82.0
    assert lcf.warnings(None, _cond({})) == []
