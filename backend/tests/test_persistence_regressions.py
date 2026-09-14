from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.analysis import analyze_match
from app.db.connection import normalize_async_url
from app.models import MatchRawData
from app.pipeline import runner


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+asyncpg"])
def test_database_url_normalized_without_losing_password(scheme):
    url = normalize_async_url(f"{scheme}://user:p%40ss@localhost/db")
    assert url.drivername == "postgresql+asyncpg"
    assert url.password == "p@ss"


@pytest.mark.asyncio
async def test_upsert_preserves_existing_scores_when_scraper_returns_null(monkeypatch):
    raw = MatchRawData(match_id="123", home_team="Home", away_team="Away", league_code="ENG PR")
    result = analyze_match(raw)
    session = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(runner, "get_session", fake_session)
    await runner._upsert(result, raw)
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    update_sql = sql.split("DO UPDATE SET", 1)[1]
    assert "actual_ft_home = coalesce(NULL, matches.actual_ft_home)" in update_sql
    assert "kickoff_time = coalesce(NULL, matches.kickoff_time)" in update_sql


@pytest.mark.asyncio
async def test_rejected_write_does_not_count_as_success():
    raw = MatchRawData(match_id="123", home_team="?", away_team="Away", league_code="ENG PR")
    with pytest.raises(ValueError, match="DB write reddedildi"):
        await runner._upsert(analyze_match(raw), raw)
