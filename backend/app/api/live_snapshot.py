"""Short lived shared livescore snapshot, with one source fetch at a time."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.scraper.fixture_scores import FixtureScore
from app.scraper.live_scores import fetch_live_scores
from app.scraper.source_board import fetch_source_board

log = logging.getLogger(__name__)
_TTL_SECONDS = 45
_LIVE_FRESH_SECONDS = 120
_lock = asyncio.Lock()
_cached: "LiveSnapshot | None" = None
_cached_at = 0.0


@dataclass(frozen=True)
class LiveSnapshot:
    scores: dict[str, FixtureScore]
    checked_at: datetime

    def live_is_fresh(self) -> bool:
        age = (datetime.now(timezone.utc) - self.checked_at).total_seconds()
        return 0 <= age < _LIVE_FRESH_SECONDS


async def get_live_snapshot() -> LiveSnapshot | None:
    global _cached, _cached_at
    if _cached is not None and time.monotonic() - _cached_at < _TTL_SECONDS:
        return _cached
    async with _lock:
        if _cached is not None and time.monotonic() - _cached_at < _TTL_SECONDS:
            return _cached
        try:
            today = datetime.now(timezone(timedelta(hours=3))).date()
            current, next_day, live = await asyncio.wait_for(asyncio.gather(
                fetch_source_board(today),
                fetch_source_board(today + timedelta(days=1)),
                fetch_live_scores(),
                return_exceptions=True,
            ), timeout=30)
            scores = {}
            for source in (current, next_day):
                if isinstance(source, dict):
                    scores.update(source)
            if isinstance(live, dict):
                for match_id, observed in live.items():
                    base = scores.get(match_id)
                    if base is None or base.status != "finished":
                        if base is None or observed.status != "scheduled":
                            scores[match_id] = observed
            if not scores:
                raise ValueError("Empty livescore board")
        except Exception as exc:
            log.warning("Canlı skor panosu okunamadı: %s", exc)
            _cached_at = time.monotonic()
            return _cached
        _cached = LiveSnapshot(scores, datetime.now(timezone.utc))
        _cached_at = time.monotonic()
        return _cached
