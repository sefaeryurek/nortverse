from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api import main as api


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, [None], [{"match_id": "123"}], "bad"])
async def test_invalid_cache_recovers_by_fetching_fixture(monkeypatch, payload):
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(cached_at=datetime.now(timezone.utc), matches_json=payload)

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(api, "get_session", get_session)
    monkeypatch.setattr(api, "_fixture_cache", {})
    monkeypatch.setattr(api, "_bg_queue", None)
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(api, "fetch_fixture", fetch)
    assert await api.fixture(None) == []
    fetch.assert_awaited_once()
    session.merge.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_naive_cache_timestamp_uses_utc(monkeypatch):
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(cached_at=datetime.now(timezone.utc).replace(tzinfo=None),
                                              matches_json=[])

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(api, "get_session", get_session)
    monkeypatch.setattr(api, "_fixture_cache", {})
    monkeypatch.setattr(api, "_bg_queue", None)
    fetch = AsyncMock()
    monkeypatch.setattr(api, "fetch_fixture", fetch)
    assert await api.fixture(None) == []
    fetch.assert_not_called()
