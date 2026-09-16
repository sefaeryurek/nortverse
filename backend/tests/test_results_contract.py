from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api import routes_results as rr
from app.db.models import Match


@pytest.mark.asyncio
async def test_results_keep_scheduled_and_unconfirmed_matches(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [Match(match_id=str(i), home_team="A", away_team="B", league_code="ENG PR",
                  kickoff_time=kickoff, actual_ft_home=h, actual_ft_away=a)
            for i, (kickoff, h, a) in enumerate([
                (now + timedelta(hours=1), None, None),
                (now - timedelta(minutes=10), None, None),
                (now - timedelta(hours=4), None, None),
                (now - timedelta(hours=4), 2, 1),
            ])]
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session = AsyncMock()
    session.execute.return_value = result

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(rr, "get_session", fake_session)
    matches = await rr.get_results("2026-09-14")
    assert [m.status for m in matches] == ["scheduled", "pending", "pending", "finished"]
    assert matches[-1].result == "1"
    assert all(m.result is None for m in matches[:-1])
