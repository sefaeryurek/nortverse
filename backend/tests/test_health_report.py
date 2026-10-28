"""Sağlık raporu canlı dondurma kuralı (Sprint 94 D4)."""

from app.cli.health_cmds import evaluate_live


def test_no_candidates_is_ok():
    assert evaluate_live([], set(), {})["ok"]


def test_alert_when_no_half_time_record():
    result = evaluate_live(["1", "2"], set(), {})
    assert not result["ok"] and "1, 2" in result["detail"]


def test_one_observation_is_enough():
    assert evaluate_live(["1", "2"], {"2"}, {})["ok"]


def test_postponed_matches_are_ignored():
    assert evaluate_live(["1"], set(), {"1": "postponed"})["ok"]
    assert not evaluate_live(["1", "2"], set(), {"1": "postponed"})["ok"]
