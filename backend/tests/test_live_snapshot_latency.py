"""A slow livescore source must not hold the bulletin or results open."""

import asyncio
import time
from datetime import datetime, timedelta

import pytest

from app.api import live_snapshot as snapshots
from app.config import ISTANBUL_TZ
from app.scraper.fixture_scores import FixtureScore


@pytest.mark.asyncio
async def test_cold_request_returns_quickly_and_single_refresh_finishes_later(monkeypatch):
    gate = asyncio.Event()
    calls = {"board": 0, "live": 0}

    async def board(_day):
        calls["board"] += 1
        await gate.wait()
        return {"101": FixtureScore("101", "finished", 2, 1)}

    async def live(budget_s=None):
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
        assert calls == {"board": 3, "live": 0}  # canlı sayfa panodan sonra, sadece gerekirse

        gate.set()
        await snapshots._refresh_task
        result = await snapshots.get_live_snapshot()
        assert result is not None
        assert result.scores["101"].status == "finished"
        assert calls["live"] == 0  # Sprint 94 F10: panoda canlı maç yok → Chromium açılmaz
    finally:
        gate.set()
        await snapshots.shutdown_live_snapshot()


@pytest.mark.asyncio
async def test_quick_board_scores_are_available_before_slow_minute_source(monkeypatch):
    gate = asyncio.Event()
    days = []

    async def board(day):
        days.append(day)
        today = datetime.now(ISTANBUL_TZ).date()
        if day == today - timedelta(days=1):
            await gate.wait()
        return {"102": FixtureScore("102", "live", 1, 0)}

    async def live(budget_s=None):
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
        today = datetime.now(ISTANBUL_TZ).date()
        assert set(days) == {today - timedelta(days=1), today, today + timedelta(days=1)}

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
        assert calls == 3
        assert await snapshots.get_live_snapshot() is None
        assert calls == 3
    finally:
        await snapshots.shutdown_live_snapshot()


@pytest.mark.asyncio
async def test_live_page_gets_remaining_budget_and_board_failure_falls_back(monkeypatch):
    """Sprint 94 F10: pano okunamazsa canlı sayfa yedek olarak denenir ve kalan bütçe verilir."""
    budgets = []

    async def board(_day):
        raise RuntimeError("pano yok")

    async def live(budget_s=None):
        budgets.append(budget_s)
        return {"103": FixtureScore("103", "live", 0, 0, minute="12")}

    monkeypatch.setattr(snapshots, "_cached", None)
    monkeypatch.setattr(snapshots, "_cached_at", 0.0)
    monkeypatch.setattr(snapshots, "_refresh_task", None)
    monkeypatch.setattr(snapshots, "_retry_after", 0.0)
    monkeypatch.setattr(snapshots, "fetch_source_board", board)
    monkeypatch.setattr(snapshots, "fetch_live_scores", live)
    try:
        result = await snapshots._refresh()
        assert result is not None and result.scores["103"].minute == "12"
        assert budgets and 0 < budgets[0] < snapshots._LIVE_BUDGET_SECONDS
    finally:
        await snapshots.shutdown_live_snapshot()
