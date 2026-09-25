import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest

from app.analysis import persist
from app.api import main as api
from app.api import routes_analysis
from app.api import services as svc


async def compute():
    return await persist.compute_all_patterns("123", ([], [], []), ([], [], []),
                                              ([], [], []), {"1-0": 3.5},
                                              as_of=datetime(2026, 9, 22, tzinfo=timezone.utc))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["ht", "h2", "ft", "c"])
async def test_failed_component_cannot_be_returned_as_empty_pattern(monkeypatch, failure):
    completed = []

    async def find_b(period, *args, **kwargs):
        await asyncio.sleep(0)
        completed.append(period)
        if failure == period:
            raise RuntimeError("connection lost")
        return None

    async def find_c(*args, **kwargs):
        await asyncio.sleep(0)
        completed.append("c")
        if failure == "c":
            raise RuntimeError("connection lost")
        return None, None, None

    monkeypatch.setattr(persist, "find_pattern_b_matches", find_b)
    monkeypatch.setattr(persist, "find_pattern_c_all_periods", find_c)
    with pytest.raises(persist.PatternComputationError):
        await compute()
    assert set(completed) == {"ht", "h2", "ft", "c"}


@pytest.mark.asyncio
async def test_successful_empty_result_remains_distinct_from_failure(monkeypatch):
    monkeypatch.setattr(persist, "find_pattern_b_matches", AsyncMock(return_value=None))
    monkeypatch.setattr(persist, "find_pattern_c_all_periods", AsyncMock(return_value=(None, None, None)))
    result = await compute()
    assert len(result) == 6
    assert all(value is None for value in result.values())


@pytest.mark.asyncio
async def test_write_failure_propagates_to_retry_caller(monkeypatch):
    session = AsyncMock()
    session.execute.side_effect = RuntimeError("connection lost")

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(persist, "get_session", get_session)
    with pytest.raises(RuntimeError, match="connection lost"):
        await persist.update_match_patterns("123", {"pattern_ft_b": None}, expected_analyzed_at=None)


@pytest.mark.asyncio
async def test_failed_refresh_is_503_and_preserves_cached_result(monkeypatch):
    monkeypatch.setattr(svc, "analysis_cache", {})
    monkeypatch.setattr(svc, "_analysis_cached_at", {})
    svc.analysis_cache["123"] = "previous"
    monkeypatch.setattr(routes_analysis, "do_analyze", AsyncMock(
        side_effect=persist.PatternComputationError("sensitive internal error")))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url="http://test") as client:
        response = await client.post("/api/analyze/123")
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert "sensitive" not in response.text
    assert svc.analysis_cache["123"] == "previous"


@pytest.mark.asyncio
async def test_background_analysis_waits_for_foreground_refresh(monkeypatch):
    worker = AsyncMock(return_value=True)
    monkeypatch.setattr(svc, "_analyze_db_only_locked", worker)
    svc._analysis_locks.pop("123", None)
    lock = svc.get_or_make_lock("123")
    async with lock:
        task = asyncio.create_task(svc._analyze_db_only("123"))
        await asyncio.sleep(0)
        worker.assert_not_called()
        assert not task.done()
    assert await task is True
    worker.assert_awaited_once_with("123")
