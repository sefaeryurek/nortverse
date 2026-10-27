"""İY oranları (scraper.odds) ve değer hesabı (ht_value)."""

import json
from datetime import datetime, timezone

from app.analysis import ht_value as hv
from app.scraper.odds import latest_prematch, parse_odds

_PAYLOAD = json.dumps({"ErrCode": 0, "Data": {
    "op": [
        {"odds": {"u": "0", "g": "0", "d": "0"}, "mt": 1700003000, "ht": "02", "type": 2},   # maç içi, atlanır
        {"odds": {"u": "2.3", "g": "2.5", "d": "4.33"}, "mt": 1700002000, "ht": "", "type": 2},
        {"odds": {"u": "2.2", "g": "2.5", "d": "4.5"}, "mt": 1700001000, "ht": "", "type": 2},
    ],
    "ou": [{"odds": {"u": "0.9", "g": "1.25", "d": "0.9"}, "mt": 1700002000, "ht": "", "type": 2}],
    "ah": [],
}})


def test_parse_and_latest_prematch_skips_in_play_and_respects_kickoff():
    history = parse_odds(_PAYLOAD)
    assert len(history["op"]) == 2  # sıfır oranlı maç içi satır atıldı
    latest = latest_prematch(history)
    assert latest["op"] == {"1": 2.3, "X": 2.5, "2": 4.33, "mt": 1700002000}
    assert latest["ou"]["line"] == 1.25 and latest["ou"]["over"] == 1.9
    before = latest_prematch(history, before=datetime.fromtimestamp(1700001500, timezone.utc))
    assert before["op"]["1"] == 2.2 and "ou" not in before


def test_parse_odds_rejects_garbage():
    assert parse_odds(b"<html>") is None


def test_asian_total_returns():
    # 1.25 üst = yarısı 1.0 (iade), yarısı 1.5 (kayıp) → toplam 1 golde −0.5
    assert hv.total_return(1, 1.25, "over", 1.9) == -0.5
    assert hv.total_return(2, 1.25, "over", 1.9) == 0.9
    assert hv.total_return(1, 1.0, "over", 1.9) == 0.0
    assert hv.total_return(0, 0.75, "under", 2.0) == 1.0
    assert hv.total_return(1, 0.75, "under", 2.0) == -0.5


def test_candidates_ev_and_decide():
    odds = {"op": {"1": 3.0, "X": 2.2, "2": 4.0}, "ou": {"line": 0.5, "over": 1.5, "under": 2.6}}
    cands = hv.candidates(0.9, 0.4, odds)
    by = {(c["market"], c["selection"]): c for c in cands}
    p1 = by[("result", "1")]
    assert abs(p1["ev"] - (p1["prob"] * 3.0 - 1)) < 1e-9
    assert abs(by[("ou", "over")]["prob"] + by[("ou", "under")]["prob"] - 1) < 1e-6
    picks = hv.decide(cands, {**hv.RULE_PARAMS, "min_ev": -1.0, "min_prob": 0.0, "max_odds": 10})
    assert len(picks) == 2 and picks[0]["ev"] >= picks[1]["ev"]  # pazar başına tek seçim
    assert hv.settle(p1, (1, 0)) == 2.0 and hv.settle(p1, (0, 0)) == -1.0
