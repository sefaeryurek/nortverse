"""Canlı İY→MS modeli, evre ayrıştırma ve devre arası dondurma kuralları."""

import gzip
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.analysis.live_model import CondTable, Counts, prematch_posterior, predict_live
from app.api import live_ledger
from app.api.live_ledger import freeze_live_prediction, ledger_rows, observed_ht
from app.scraper.fixture_scores import FixtureScore, phase_from_minute
from app.scraper.live_scores import parse_live_scores
from app.scraper.source_board import parse_source_board

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
LEAGUE = "English Premier League"


def _table(rows):
    table = CondTable(cutoff=NOW, prior_from=NOW - timedelta(days=1000))
    for league, ht, ft in rows:
        table.add(league, *ht, *ft, NOW - timedelta(days=10))
    return table


def _many(league, ht, ft, n):
    return [(league, ht, ft)] * n


# ─── Model ────────────────────────────────────────────────────────────────

def test_cond_uses_same_ht_score_when_enough_samples():
    table = _table(_many(LEAGUE, (1, 0), (2, 0), 40) + _many(LEAGUE, (1, 0), (1, 1), 10))
    level, counts = table.cond(LEAGUE, (1, 0))
    assert level == "score" and counts.n == 50


def test_cond_falls_back_to_goal_difference_then_global():
    table = _table(_many(LEAGUE, (2, 1), (2, 1), 35) + _many("Spanish La Liga", (3, 2), (3, 2), 40))
    assert table.cond(LEAGUE, (1, 0))[0] == "diff"          # aynı fark (+1) ligde 35
    assert table.cond("Italy Serie A", (1, 0))[0] == "global_diff"


def test_laplace_never_claims_certainty():
    dist = Counts(n1=30).result_dist()
    assert dist["1"] < 1 and dist["X"] > 0


def test_prematch_posterior_pools_and_shrinks_to_prior():
    prior = {"1": 0.45, "X": 0.25, "2": 0.30}
    blob = {"match_count": 20, "result_1_pct": 80.0, "result_x_pct": 10.0, "result_2_pct": 10.0}
    post, n = prematch_posterior([blob, None], prior, k=20)
    assert n == 20
    assert post["1"] == pytest.approx((16 + 9) / 40)
    assert prematch_posterior([None], prior) is None


def test_predict_live_lr_shifts_toward_prematch_view():
    rows = (_many(LEAGUE, (0, 0), (1, 0), 37) + _many(LEAGUE, (0, 0), (0, 0), 37)
            + _many(LEAGUE, (0, 0), (0, 1), 26))
    table = _table(rows)
    strong_home = {"match_count": 100, "result_1_pct": 75.0, "result_x_pct": 15.0, "result_2_pct": 10.0}
    without = predict_live(table, LEAGUE, (0, 0), [])
    with_lr = predict_live(table, LEAGUE, (0, 0), [strong_home])
    assert without["ms"]["prematch"] is None
    assert with_lr["ms"]["probs"]["1"] > without["ms"]["probs"]["1"]
    assert sum(with_lr["ms"]["probs"].values()) == pytest.approx(1, abs=1e-3)


def test_predict_live_market_applicability_and_tiers():
    table = _table(_many(LEAGUE, (2, 1), (3, 1), 40) + _many(LEAGUE, (0, 0), (0, 0), 40))
    already = predict_live(table, LEAGUE, (2, 1), [])
    assert already["over25"] == {"applicable": False, "reason": "already_over"}
    assert already["btts"] == {"applicable": False, "reason": "already_both"}
    assert already["ms"]["tier"] == "high"
    goalless = predict_live(table, LEAGUE, (0, 0), [])
    assert goalless["over25"]["pick"] == "under" and goalless["btts"]["pick"] == "no"


def test_insufficient_tier_when_no_data():
    assert predict_live(_table([]), LEAGUE, (4, 4), [])["ms"]["tier"] == "insufficient"


# ─── Evre ayrıştırma ──────────────────────────────────────────────────────

def test_phase_from_minute():
    assert phase_from_minute("HT") == "ht"
    assert phase_from_minute("45+2") == "1h"
    assert phase_from_minute("46") == "2h"
    assert phase_from_minute(None) is None


def test_source_board_status_codes_map_to_phase_and_ht_score():
    data = "\r\n".join([
        "A[1]=[201,1,2,3,'A','B','2026,8,19,12,00,00',2,1,0,,,0];",
        "A[2]=[202,1,2,3,'C','D','2026,8,19,12,00,00',3,2,1,1,1,0];",
        "A[3]=[203,1,2,3,'E','F','2026,8,19,12,00,00',1,0,0,,,0];",
    ])
    scores = parse_source_board(gzip.compress(json.dumps({"ErrCode": 0, "Data": data}).encode()))
    assert (scores["201"].phase, scores["201"].minute, scores["201"].ht_home, scores["201"].ht_away) == ("ht", "HT", 1, 0)
    assert (scores["202"].phase, scores["202"].ht_home) == ("2h", 1)
    assert scores["203"].phase == "1h"


def test_live_page_second_half_label_keeps_phase():
    html = '<tr id="tr1_301"><td class="status">2nd Half</td><td class="f-b blue">1 - 0</td></tr>'
    fs = parse_live_scores(html)["301"]
    assert (fs.status, fs.minute, fs.phase) == ("live", None, "2h")


def test_observed_ht_by_phase():
    assert observed_ht(FixtureScore("1", "live", 1, 0, minute="HT")) == (1, 0)
    assert observed_ht(FixtureScore("1", "live", 2, 0, ht_home=1, ht_away=0, phase="2h")) == (1, 0)
    assert observed_ht(FixtureScore("1", "live", 2, 0, phase="2h")) is None
    assert observed_ht(FixtureScore("1", "live", 0, 0, minute="30")) is None


# ─── Dondurma ─────────────────────────────────────────────────────────────

def _match(**kw):
    base = dict(match_id="900", league_name=LEAGUE, kickoff_time=NOW,
                pattern_ft_b=None, pattern_ft_c=None, pattern_ft_d=None,
                pattern_b_hash="b1", pattern_c_hash=None, pattern_d_hash="d1")
    base.update(kw)
    return SimpleNamespace(**base)


def test_ledger_rows_contain_ms_and_applicable_goal_markets():
    table = _table(_many(LEAGUE, (1, 0), (2, 0), 40))
    prediction = predict_live(table, LEAGUE, (1, 0), [])
    rows = ledger_rows(_match(), prediction, NOW + timedelta(minutes=50), 7, late=False)
    markets = [r["market"] for r in rows]
    assert markets == ["result", "ou_25", "kg"]
    ms = rows[0]
    assert ms["source"] == "live_ht" and ms["selection"] == "1" and ms["ht_observation_id"] == 7
    assert ms["pattern_hash"] == "b=b1;d=d1"
    assert ms["details"]["ms"]["pick"] == "1" and ms["details"]["late"] is False


@pytest.mark.asyncio
async def test_freeze_skips_second_half_when_score_changed(monkeypatch):
    monkeypatch.setattr(live_ledger, "get_cond_table", AsyncMock(side_effect=AssertionError("hesaplanmamalı")))
    fs = FixtureScore("900", "live", 2, 0, ht_home=1, ht_away=0, phase="2h")
    match = _match(kickoff_time=datetime.now(timezone.utc) - timedelta(minutes=70))
    assert await freeze_live_prediction(match, fs) == "late_score_changed"


@pytest.mark.asyncio
async def test_freeze_dry_run_computes_without_writing(monkeypatch):
    monkeypatch.setattr(live_ledger, "get_cond_table", AsyncMock(return_value=_table(_many(LEAGUE, (1, 0), (1, 0), 40))))
    monkeypatch.setattr(live_ledger, "get_session", lambda: (_ for _ in ()).throw(AssertionError("yazmamalı")))
    fs = FixtureScore("900", "live", 1, 0, minute="HT")
    match = _match(kickoff_time=datetime.now(timezone.utc) - timedelta(minutes=50))
    assert await freeze_live_prediction(match, fs, dry_run=True) == "dry_run"


@pytest.mark.asyncio
async def test_freeze_requires_ht_phase():
    fs = FixtureScore("900", "live", 0, 0, minute="30")
    assert await freeze_live_prediction(_match(), fs) == "no_ht"


@pytest.mark.asyncio
async def test_run_tick_dry_run_reports_every_candidate_without_writing(monkeypatch):
    from contextlib import asynccontextmanager

    kickoff = datetime.now(timezone.utc) - timedelta(minutes=55)
    ht_match = _match(match_id="1", kickoff_time=kickoff)
    first_half = _match(match_id="2", kickoff_time=kickoff)
    missing = _match(match_id="3", kickoff_time=kickoff)
    done = _match(match_id="4", kickoff_time=kickoff)
    results = iter([[ht_match, first_half, missing, done], ["4"]])

    class _Result:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return self

        def all(self):
            return self._items

    class _Session:
        async def execute(self, _stmt):
            return _Result(next(results))

    @asynccontextmanager
    async def fake_session():
        yield _Session()

    monkeypatch.setattr(live_ledger, "get_session", fake_session)
    monkeypatch.setattr(live_ledger, "record_predictions", AsyncMock(side_effect=AssertionError("yazmamalı")))
    monkeypatch.setattr(live_ledger, "get_cond_table", AsyncMock(return_value=_table(_many(LEAGUE, (1, 0), (1, 0), 40))))
    snapshot = SimpleNamespace(scores={
        "1": FixtureScore("1", "live", 1, 0, minute="HT"),
        "2": FixtureScore("2", "live", 0, 0, minute="30"),
    })
    report = await live_ledger.run_tick(dry_run=True, snapshot=snapshot)
    status = {e["match"].match_id: e["status"] for e in report}
    assert status == {"4": "already_frozen", "1": "dry_run", "2": "no_ht", "3": "not_live"}
    assert next(e for e in report if e["match"].match_id == "1")["prediction"]["ms"]["pick"] == "1"
