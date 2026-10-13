"""live_snapshot.py model + helper testleri."""

from datetime import datetime, timezone

from app.api.live_snapshot import LiveSnapshot, _TTL_SECONDS, _LIVE_FRESH_SECONDS
from app.scraper.fixture_scores import FixtureScore


class TestLiveSnapshotModel:
    def test_fresh_snapshot(self):
        snap = LiveSnapshot(scores={}, checked_at=datetime.now(timezone.utc))
        assert snap.live_is_fresh()

    def test_stale_snapshot(self):
        from datetime import timedelta
        old = datetime.now(timezone.utc) - timedelta(seconds=_LIVE_FRESH_SECONDS + 1)
        snap = LiveSnapshot(scores={}, checked_at=old)
        assert not snap.live_is_fresh()

    def test_frozen_dataclass(self):
        snap = LiveSnapshot(scores={}, checked_at=datetime.now(timezone.utc))
        import dataclasses
        assert dataclasses.is_dataclass(snap)
        try:
            snap.scores = {}
            assert False, "Should be frozen"
        except (AttributeError, dataclasses.FrozenInstanceError):
            pass

    def test_scores_dict(self):
        score = FixtureScore(match_id="123", status="finished", home=2, away=1)
        snap = LiveSnapshot(
            scores={"123": score},
            checked_at=datetime.now(timezone.utc),
        )
        assert snap.scores["123"].home == 2
        assert snap.scores["123"].status == "finished"


class TestFixtureScoreModel:
    def test_defaults(self):
        fs = FixtureScore(match_id="1", status="scheduled")
        assert fs.home is None
        assert fs.away is None
        assert fs.ht_home is None
        assert fs.minute is None

    def test_full_score(self):
        fs = FixtureScore("1", "finished", 3, 1, 1, 0, None)
        assert fs.home == 3
        assert fs.ht_home == 1

    def test_live_with_minute(self):
        fs = FixtureScore("1", "live", 1, 0, minute="45+2")
        assert fs.minute == "45+2"


class TestConstants:
    def test_ttl_seconds(self):
        assert _TTL_SECONDS == 45

    def test_live_fresh_seconds(self):
        assert _LIVE_FRESH_SECONDS == 120
