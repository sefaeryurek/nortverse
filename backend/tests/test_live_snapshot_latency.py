"""A slow livescore source must not hold the bulletin or results open."""

import asyncio
import time

import pytest

from app.api import live_snapshot as snapshots
from app.scraper.fixture_scores import FixtureScore


@pytest.mark.asyncio
async def test_cold_request_returns_quickly_and_single_refresh_finishes_later(monkeypatch):
    gate = asyncio.Event()
    calls = {"board": 0, "live": 0}

    async def board(_day):
        calls["board"] += 1
        await gate.wait()
        return {"101": FixtureScore("101", "finished", 2, 1)}

    async def live():
        calls["live"] += 1
        await gate.wait()
        return {}

    monkeypatch.setattr(snapshots, "_cached", None)
    monkeypatch.setattr(snapshots, "_cached_at", 0.0)
    monkeypatch.setattr(snapshots, "_refresh_task", None)
    monkeypatch.setattr(snapshots, "_retry_after", 0.0)
    monkeypatch.setattr(snapshots, "_COLD_WAIT_SECONDS", 0.01)
    monkeypatch.setattr(snapshots, "fetch_source_board", board)
    monkeypatch.setattr(snapshots, "fetch_live_scores", live)

    start = time.monotonic()
    try:
        assert await snapshots.get_live_snapshot() is None
        assert time.monotonic() - start < 0.2
        assert await snapshots.get_live_snapshot() is None
        assert calls == {"board": 2, "live": 1}

        gate.set()
        await snapshots._refresh_task
        result = await snapshots.get_live_snapshot()
        assert result is not None
        assert result.scores["101"].status == "finished"
    finally:
        gate.set()
        await snapshots.shutdown_live_snapshot()


@pytest.mark.asyncio
async def test_quick_board_scores_are_available_before_slow_minute_source(monkeypatch):
    gate = asyncio.Event()

    async def board(_day):
        return {"102": FixtureScore("102", "live", 1, 0)}

    async def live():
        await gate.wait()
        return {"102": FixtureScore("102", "live", 1, 0, minute="67")}

    monkeypatch.setattr(snapshots, "_cached", None)
    monkeypatch.setattr(snapshots, "_cached_at", 0.0)
    monkeypatch.setattr(snapshots, "_refresh_task", None)
    monkeypatch.setattr(snapshots, "_retry_after", 0.0)
    monkeypatch.setattr(snapshots, "_COLD_WAIT_SECONDS", 0.02)
    monkeypatch.setattr(snapshots, "fetch_source_board", board)
    monkeypatch.setattr(snapshots, "fetch_live_scores", live)

    try:
        partial = await snapshots.get_live_snapshot()
        assert partial is not None
        assert partial.scores["102"].status == "live"
        assert partial.scores["102"].minute is None

        gate.set()
        await snapshots._refresh_task
        complete = await snapshots.get_live_snapshot()
        assert complete is not None
        assert complete.scores["102"].minute == "67"
    finally:
        gate.set()
        await snapshots.shutdown_live_snapshot()


@pytest.mark.asyncio
async def test_failed_source_uses_retry_backoff(monkeypatch):
    calls = 0

    async def failed_board(_day):
        nonlocal calls
        calls += 1
        raise RuntimeError("source down")

    async def empty_live():
        return {}

    monkeypatch.setattr(snapshots, "_cached", None)
    monkeypatch.setattr(snapshots, "_cached_at", 0.0)
    monkeypatch.setattr(snapshots, "_refresh_task", None)
    monkeypatch.setattr(snapshots, "_retry_after", 0.0)
    monkeypatch.setattr(snapshots, "fetch_source_board", failed_board)
    monkeypatch.setattr(snapshots, "fetch_live_scores", empty_live)

    try:
        assert await snapshots.get_live_snapshot() is None
        assert calls == 2
        assert await snapshots.get_live_snapshot() is None
        assert calls == 2
    finally:
        await snapshots.shutdown_live_snapshot()
