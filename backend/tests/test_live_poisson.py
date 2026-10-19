"""Gölge Poisson canlı modeli (live-poisson-v1): takım gücü, 2Y payı, pazar olasılıkları, defter satırları."""

import random
from datetime import datetime, timedelta, timezone

import pytest

from app.analysis import live_poisson as lp

AS_OF = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
LEAGUE = "English Premier League"


def _season(n=400, seed=7):
    """Güçlü (Strong) her maçta çok atar, zayıf (Weak) az; diğerleri ortalama."""
    rng = random.Random(seed)
    teams = ["Strong", "Weak"] + [f"T{i}" for i in range(8)]
    power = {"Strong": 1.0, "Weak": -0.8}
    rows = []
    for k in range(n):
        home, away = rng.sample(teams, 2)
        lam_h = 1.5 * pow(2.718, power.get(home, 0) - power.get(away, 0) * 0.5)
        lam_a = 1.1 * pow(2.718, power.get(away, 0) - power.get(home, 0) * 0.5)
        ft_h, ft_a = _poisson(rng, lam_h), _poisson(rng, lam_a)
        ht_h, ht_a = rng.randint(0, ft_h), rng.randint(0, ft_a)
        rows.append(lp.TrainMatch(AS_OF - timedelta(days=n - k), LEAGUE, home, away, ht_h, ht_a, ft_h, ft_a))
    return rows


def _poisson(rng, lam):
    import math
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def test_rule_params_fingerprint_is_pinned():
    # Model parametresi değişirse kural sürümü (LIVE_POISSON_RULE_VERSION) artırılmalı.
    assert lp.LIVE_POISSON_RULE_VERSION == "live-poisson-v1"
    assert lp.rule_params_fingerprint() == "0882f85814ef"


def test_fit_ranks_strong_team_above_weak():
    model = lp.fit_model(_season(), AS_OF)
    lm = model.leagues[LEAGUE]
    assert lm.attack["Strong"] > 0 > lm.attack["Weak"]
    assert set(lm.share) == set(lp.STATES)
    assert all(isinstance(v, float) for pair in lm.share.values() for v in pair)


def test_small_league_has_no_model():
    assert lp.fit_model(_season(n=50), AS_OF).leagues == {}


def test_predict_probabilities_are_consistent():
    model = lp.fit_model(_season(), AS_OF)
    pred = lp.predict(model, LEAGUE, "Strong", "Weak", (2, 0))
    cells = {(c["period"], c["market"]): c for c in pred["cells"]}
    for (_, market), cell in cells.items():
        # ÇŞ seçimleri örtüşür (1X, X2, 12): toplam %200
        assert sum(cell["options"].values()) == pytest.approx(200 if market == "dc" else 100, abs=0.5)
    assert cells[("ft", "result")]["selection"] == "1"
    assert ("ft", "ou_15") not in cells          # İY 2-0: Üst 1.5 zaten kesin
    assert pred["lambda_2h"]["home"] > pred["lambda_2h"]["away"]
    assert lp.predict(model, "Unknown League", "A", "B", (0, 0)) is None


def test_decisions_flag_valuable_and_best():
    pred = {"cells": [
        {"period": "ft", "market": "dc", "selection": "1X", "pct": 95.0, "options": {}},
        {"period": "ft", "market": "ou_35", "selection": "under", "pct": 88.0, "options": {}},
        {"period": "ft", "market": "ou_25", "selection": "under", "pct": 70.0, "options": {}},
    ], "lambda_2h": {}, "lambda_ft": {}}
    cond = {("ft", "dc", "1X"): {"pct": 93.0, "n": 200, "level": "league"}}
    picks = lp.decisions(pred, lambda p, m, s: cond.get((p, m, s)))
    assert [p["market"] for p in picks] == ["dc", "ou_35"]          # %85 altı yok
    by = {p["market"]: p for p in picks}
    assert by["dc"]["best"] and not by["ou_35"]["best"]
    assert by["dc"]["valuable"] is False and by["ou_35"]["valuable"] is True   # COND yok → değerli
    rows = lp.ledger_rows(pred, picks, {"match_id": "1"})
    assert {r["rule_version"] for r in rows} == {"live-poisson-v1"}
    assert all(r["details"]["shadow"] for r in rows) and rows[0]["prob_shown_bp"] == 9500


def test_train_window_excludes_recent_and_old():
    rows = _season(n=1200)
    kickoffs = [r.kickoff for r in rows]
    window = lp.train_window(rows, kickoffs, AS_OF)
    assert window and window[-1].kickoff <= AS_OF - timedelta(hours=3)
    assert window[0].kickoff >= AS_OF - timedelta(days=lp.RULE_PARAMS["train_days"])
