"""score_state.py birim testleri — resolve_match_state karar mantığı."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.config import ISTANBUL_TZ
from app.api.score_state import MatchState, resolve_match_state, _utc, LIVE_FRESH_SECONDS
from app.scraper.fixture_scores import FixtureScore


NOW = datetime(2026, 10, 11, 15, 0, 0, tzinfo=timezone.utc)


def _item(**kw) -> dict:
    return {"score_checked_at": None, "score_status": None, "score_home": None,
            "score_away": None, "live_minute": None, **kw}


# ─── _utc yardımcısı ──────────────────────────────────────────────────────────

class TestUtc:
    def test_none(self):
        assert _utc(None) is None

    def test_naive_datetime(self):
        dt = datetime(2026, 1, 1, 12, 0, 0)
        result = _utc(dt)
        assert result is not None
        assert result.tzinfo == timezone.utc

    def test_aware_datetime(self):
        dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=ISTANBUL_TZ)
        result = _utc(dt)
        assert result is not None
        assert result.tzinfo == timezone.utc
        assert result.hour == 9

    def test_iso_string(self):
        result = _utc("2026-10-01T14:00:00")
        assert result is not None
        assert result.tzinfo == timezone.utc

    def test_invalid_string(self):
        assert _utc("not-a-date") is None

    def test_empty_string(self):
        assert _utc("") is None


# ─── resolve_match_state ──────────────────────────────────────────────────────

def _obs(status="finished", home=None, away=None, minute=None):
    return FixtureScore(match_id="100", status=status, home=home, away=away, minute=minute)


class TestResolveFinished:
    def test_observed_finished(self):
        obs = _obs(status="finished", home=2, away=1)
        obs_at = NOW - timedelta(minutes=5)
        state = resolve_match_state(_item(), None, None, None, obs, obs_at, NOW)
        assert state.status == "finished"
        assert state.final_home == 2
        assert state.final_away == 1

    def test_actual_scores(self):
        state = resolve_match_state(_item(), None, 3, 0, None, None, NOW)
        assert state.status == "finished"
        assert state.final_home == 3
        assert state.final_away == 0

    def test_item_finished(self):
        item = _item(score_status="finished", score_home=1, score_away=1)
        state = resolve_match_state(item, None, None, None, None, None, NOW)
        assert state.status == "finished"
        assert state.final_home == 1
        assert state.final_away == 1

    def test_observed_finished_takes_precedence_over_actual(self):
        obs = _obs(status="finished", home=2, away=0)
        state = resolve_match_state(_item(), None, 1, 1, obs, NOW, NOW)
        assert state.final_home == 2
        assert state.final_away == 0


class TestResolvePostponed:
    def test_observed_postponed(self):
        obs = _obs(status="postponed")
        state = resolve_match_state(_item(), None, None, None, obs, NOW, NOW)
        assert state.status == "postponed"

    def test_item_postponed(self):
        item = _item(score_status="postponed")
        state = resolve_match_state(item, None, None, None, None, None, NOW)
        assert state.status == "postponed"


class TestResolveScheduled:
    def test_observed_scheduled(self):
        obs = _obs(status="scheduled")
        state = resolve_match_state(_item(), None, None, None, obs, NOW, NOW)
        assert state.status == "scheduled"

    def test_no_data_before_kickoff(self):
        kickoff = NOW + timedelta(hours=1)
        state = resolve_match_state(_item(), kickoff, None, None, None, None, NOW)
        assert state.status == "scheduled"


class TestResolveLive:
    def test_observed_live_fresh(self):
        obs = _obs(status="live", home=1, away=0, minute="35'")
        obs_at = NOW - timedelta(seconds=30)
        state = resolve_match_state(_item(), None, None, None, obs, obs_at, NOW)
        assert state.status == "live"
        assert state.live_home == 1
        assert state.live_away == 0
        assert state.live_minute == "35'"

    def test_observed_live_stale(self):
        obs = _obs(status="live", home=1, away=0, minute="35'")
        obs_at = NOW - timedelta(seconds=LIVE_FRESH_SECONDS + 10)
        kickoff = NOW - timedelta(hours=1)
        state = resolve_match_state(_item(), kickoff, None, None, obs, obs_at, NOW)
        assert state.status == "pending"

    def test_item_live_fresh(self):
        checked_at = (NOW - timedelta(seconds=30)).isoformat()
        item = _item(score_status="live", score_home=2, score_away=1,
                     live_minute="60'", score_checked_at=checked_at)
        state = resolve_match_state(item, None, None, None, None, None, NOW)
        assert state.status == "live"
        assert state.live_home == 2
        assert state.live_away == 1

    def test_item_live_stale(self):
        checked_at = (NOW - timedelta(seconds=LIVE_FRESH_SECONDS + 30)).isoformat()
        item = _item(score_status="live", score_home=1, score_away=0,
                     score_checked_at=checked_at)
        kickoff = NOW - timedelta(hours=1)
        state = resolve_match_state(item, kickoff, None, None, None, None, NOW)
        assert state.status == "pending"


class TestResolvePending:
    def test_past_kickoff_no_data(self):
        kickoff = NOW - timedelta(minutes=30)
        state = resolve_match_state(_item(), kickoff, None, None, None, None, NOW)
        assert state.status == "pending"


class TestScoreCheckedAt:
    def test_observed_sets_checked_at(self):
        obs = _obs(status="finished", home=1, away=0)
        obs_at = NOW - timedelta(minutes=2)
        state = resolve_match_state(_item(), None, None, None, obs, obs_at, NOW)
        assert state.score_checked_at == obs_at.isoformat()

    def test_item_checked_at_fallback(self):
        item = _item(score_checked_at="2026-10-11T14:00:00")
        state = resolve_match_state(item, NOW + timedelta(hours=2), None, None, None, None, NOW)
        assert state.score_checked_at == "2026-10-11T14:00:00"
