"""Canlı 2. yarı gölge kuralı (live-2h-v1): güvenli alt + gol işaretleri."""

import math

from app.analysis import live_2h


def _grid(ht, r_h, r_a, n=10):
    def pmf(lam):
        return [math.exp(-lam) * lam ** k / math.factorial(k) for k in range(n)]
    ph, pa = pmf(r_h), pmf(r_a)
    return [((ht[0], ht[1], ht[0] + i, ht[1] + j), ph[i] * pa[j]) for i in range(n) for j in range(n)]


def _cond(pct, n=200, level="league"):
    return lambda *_: {"pct": pct, "n": n, "level": level}


def test_rule_params_fingerprint_is_pinned():
    # Kural değişirse bu test kırılır: sabiti güncelle VE LIVE_2H_RULE_VERSION'ı artır.
    assert (live_2h.LIVE_2H_RULE_VERSION, live_2h.rule_params_fingerprint()) == ("live-2h-v1", "e7d28833d597")


def test_safe_under_needs_cond_gate():
    grid = _grid((0, 0), 0.6, 0.2)   # deplasman 2. yarıda neredeyse atamıyor
    with_cond = live_2h.decide(grid, (0, 0), _cond(90.0))
    assert any(p["kind"] == "safe" and p["market"] == "dep_15" for p in with_cond)
    assert not any(p["kind"] == "safe" for p in live_2h.decide(grid, (0, 0), lambda *_: None))


def test_safe_probability_is_min_of_poisson_and_cond():
    picks = live_2h.decide(_grid((0, 0), 0.6, 0.2), (0, 0), _cond(86.0))
    dep = next(p for p in picks if p["market"] == "dep_15")
    assert dep["pct"] == 86.0 and dep["poisson_pct"] > 86.0
    assert dep["trivial"] is True   # lig + İY geçmişi zaten ≥%80


def test_equivalent_events_counted_once():
    # İY 0-0: MS dep 1.5 alt = 2Y dep 1.5 alt → tek karar (ilk sıradaki MS kalır)
    picks = live_2h.decide(_grid((0, 0), 0.6, 0.2), (0, 0), _cond(90.0))
    dep = [p for p in picks if p["market"] == "dep_15"]
    assert [p["period"] for p in dep] == ["ft"]
    # İY 1-0: MS KG var = 2Y deplasman gol atar → biri yazılır
    goal = live_2h.decide(_grid((1, 0), 0.8, 1.8), (1, 0), _cond(60.0))
    events = {(p["period"], p["market"]) for p in goal if p["kind"] == "goal"}
    assert ("h2", "dep_05") in events and ("ft", "kg") not in events


def test_markets_decided_by_ht_are_skipped():
    picks = live_2h.decide(_grid((2, 0), 2.5, 0.1), (2, 0), _cond(95.0))
    assert not any(p["period"] == "ft" and p["market"] in ("ev_05", "ev_15") for p in picks)


def test_goal_signal_needs_seventy_percent_poisson():
    strong = live_2h.decide(_grid((0, 0), 1.5, 0.3), (0, 0), _cond(55.0))
    assert any(p["kind"] == "goal" and p["market"] == "ev_05" and p["pct"] >= 70 for p in strong)
    weak = live_2h.decide(_grid((0, 0), 0.7, 0.3), (0, 0), _cond(55.0))
    assert not any(p["kind"] == "goal" and p["market"] == "ev_05" for p in weak)


def test_no_model_no_decision():
    assert live_2h.decide(None, (0, 0), _cond(90.0)) == []


def test_ledger_rows_are_shadow():
    picks = live_2h.decide(_grid((0, 0), 1.5, 0.2), (0, 0), _cond(90.0))
    rows = live_2h.ledger_rows(picks, {"match_id": "1"}, lambdas={"2h": {}}, late=False)
    assert rows and all(r["rule_version"] == "live-2h-v1" and r["details"]["shadow"] for r in rows)
    assert {r["confidence_tier"] for r in rows} <= {"high", "medium"}
