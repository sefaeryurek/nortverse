"""Ayar parmak izi, bayat aile tespiti ve pattern as_of kuralı testleri."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

import app.api.services as svc
from app.analysis import persist
from app.db.models import Match

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _row(**kw) -> Match:
    base = dict(match_id="1", home_team="H", away_team="A", ft_scores_1=[], analyzed_at=T0)
    base.update(kw)
    return Match(**base)


class TestPatternAsOf:
    def test_pre_match_analysis_uses_analyzed_at(self):
        assert persist.pattern_as_of(T0, T0 + timedelta(days=1)) == T0

    def test_post_match_analysis_uses_kickoff(self):
        kickoff = T0 - timedelta(days=400)
        assert persist.pattern_as_of(T0, kickoff) == kickoff

    def test_missing_kickoff_uses_analyzed_at(self):
        assert persist.pattern_as_of(T0, None) == T0


class TestHashes:
    def test_hashes_stable(self):
        assert persist.pattern_hashes() == persist.pattern_hashes()

    def test_each_family_has_hash(self):
        assert set(persist.pattern_hashes()) == {"b", "c", "d"}

    def test_never_computed_is_all_stale(self):
        assert persist.stale_families(_row()) == ["b", "c", "d"]

    def test_only_mismatched_family_is_stale(self):
        h = persist.pattern_hashes()
        row = _row(pattern_computed_at=T0, pattern_b_hash=h["b"], pattern_c_hash=h["c"], pattern_d_hash="old")
        assert persist.stale_families(row) == ["d"]

    def test_hash_columns_only_for_complete_families(self):
        patterns = {k: None for k in persist.pattern_keys("c")}
        patterns["pattern_ft_d"] = None
        assert set(persist.hash_columns(patterns)) == {"pattern_c_hash"}


class TestReadPathRecompute:
    @pytest.mark.asyncio
    async def test_finished_stale_match_keeps_stored_patterns(self, monkeypatch):
        compute = AsyncMock(return_value={})
        monkeypatch.setattr(svc, "compute_all_patterns", compute)
        monkeypatch.setattr(svc, "_frozen_recommendations", AsyncMock(return_value=[]))
        row = _row(pattern_computed_at=T0, kickoff_time=T0 + timedelta(hours=1))
        await svc.build_from_db(row)
        compute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upcoming_match_recomputes_only_stale_family(self, monkeypatch):
        h = persist.pattern_hashes()
        compute = AsyncMock(return_value={k: None for k in persist.pattern_keys("d")})
        write = AsyncMock()
        monkeypatch.setattr(svc, "compute_all_patterns", compute)
        monkeypatch.setattr(svc, "update_match_patterns", write)
        monkeypatch.setattr(svc, "_frozen_recommendations", AsyncMock(return_value=[]))
        row = _row(
            pattern_computed_at=T0, kickoff_time=datetime.now(timezone.utc) + timedelta(days=1),
            pattern_b_hash=h["b"], pattern_c_hash=h["c"], pattern_d_hash="old",
        )
        await svc.build_from_db(row)
        assert compute.await_args.kwargs["families"] == ["d"]
        write.assert_awaited_once()
