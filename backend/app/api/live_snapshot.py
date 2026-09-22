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
_COLD_WAIT_SECONDS = 2.0
_RETRY_DELAY_SECONDS = 15.0
_lock = asyncio.Lock()
_cached: "LiveSnapshot | None" = None
_cached_at = 0.0
_refresh_task: "asyncio.Task[LiveSnapshot | None] | None" = None
_retry_after = 0.0


@dataclass(frozen=True)
class LiveSnapshot:
    scores: dict[str, FixtureScore]
    checked_at: datetime

    def live_is_fresh(self) -> bool:
        age = (datetime.now(timezone.utc) - self.checked_at).total_seconds()
        return 0 <= age < _LIVE_FRESH_SECONDS


async def _refresh() -> LiveSnapshot | None:
    global _cached, _cached_at, _retry_after
    started_at = time.monotonic()
    today = datetime.now(timezone(timedelta(hours=3))).date()
    live_task = asyncio.create_task(fetch_live_scores())
    board_days = (today - timedelta(days=1), today, today + timedelta(days=1))

    async def fetch_day(day):
        return day, await fetch_source_board(day)

    board_tasks = [asyncio.create_task(fetch_day(day)) for day in board_days]
    try:
        scores = {}
        board_results = {}
        try:
            for completed in asyncio.as_completed(board_tasks, timeout=20):
                try:
                    day, source = await completed
                except Exception as exc:
                    log.debug("Günlük skor panosu okunamadı: %s", exc)
                    continue
                if not isinstance(source, dict):
                    continue
                board_results[day] = source
                scores = {}
                for ordered_day in board_days:
                    scores.update(board_results.get(ordered_day, {}))
                if scores:
                    # Publish each completed day without waiting for a slower source.
                    _cached = LiveSnapshot(dict(scores), datetime.now(timezone.utc))
                    _cached_at = time.monotonic()
        except asyncio.TimeoutError:
            log.debug("Skor panolarından biri 20 saniyede tamamlanmadı")
        try:
            remaining = max(0.001, 30 - (time.monotonic() - started_at))
            live = await asyncio.wait_for(live_task, timeout=remaining)
        except Exception as exc:
            log.debug("Canlı dakika kaynağı okunamadı: %s", exc)
            live = None
        if isinstance(live, dict):
            for match_id, observed in live.items():
                base = scores.get(match_id)
                if base is None or base.status != "finished":
                    if base is None or observed.status != "scheduled":
                        scores[match_id] = observed
        if not scores:
            raise ValueError("Empty livescore board")
        _cached = LiveSnapshot(dict(scores), datetime.now(timezone.utc))
        _cached_at = time.monotonic()
        return _cached
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.warning("Canlı skor panosu okunamadı: %s", exc)
        _retry_after = time.monotonic() + _RETRY_DELAY_SECONDS
        return None
    finally:
        for task in board_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*board_tasks, return_exceptions=True)
        if not live_task.done():
            live_task.cancel()
            try:
                await live_task
            except asyncio.CancelledError:
                pass


async def get_live_snapshot() -> LiveSnapshot | None:
    """Serve recent scores promptly while a single refresh runs in the background."""
    global _refresh_task
    age = time.monotonic() - _cached_at
    if _cached is not None and age < _TTL_SECONDS:
        return _cached

    async with _lock:
        age = time.monotonic() - _cached_at
        if _cached is not None and age < _TTL_SECONDS:
            return _cached
        started_now = False
        if (_refresh_task is None or _refresh_task.done()) and time.monotonic() >= _retry_after:
            _refresh_task = asyncio.create_task(_refresh())
            started_now = True
        task = _refresh_task
        # Live minutes must not remain visible when a source is unavailable.
        stale = _cached if _cached is not None and age < _LIVE_FRESH_SECONDS else None

    if stale is not None:
        return stale
    if task is None or not started_now:
        return None
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=_COLD_WAIT_SECONDS)
    except asyncio.TimeoutError:
        return _cached if _cached is not None and time.monotonic() - _cached_at < _LIVE_FRESH_SECONDS else None


async def shutdown_live_snapshot() -> None:
    global _refresh_task
    task = _refresh_task
    _refresh_task = None
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
