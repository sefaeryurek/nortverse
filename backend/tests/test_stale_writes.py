from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.analysis import analyze_match, persist
from app.models import MatchRawData
from app.pipeline import runner
from app.api import main as api
from app.db.models import Match
from fastapi import HTTPException


def session_for(monkeypatch, module, rowcount):
    session = AsyncMock()
    session.execute.return_value = MagicMock(rowcount=rowcount)

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(module, "get_session", get_session)
    return session


@pytest.mark.asyncio
@pytest.mark.parametrize("version", [None, datetime(2026, 9, 14, tzinfo=timezone.utc)])
async def test_pattern_write_requires_same_source_version_and_active_row(monkeypatch, version):
    session = session_for(monkeypatch, persist, 1)
    await persist.update_match_patterns("123", {"pattern_ft_b": None}, expected_analyzed_at=version)
    stmt = session.execute.call_args.args[0]
    compiled = stmt.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "matches.deleted_at IS NULL" in sql
    if version is None:
        assert "matches.analyzed_at IS NULL" in sql
    else:
        assert "matches.analyzed_at =" in sql
        assert version in compiled.params.values()


@pytest.mark.asyncio
async def test_stale_pattern_write_is_not_reported_as_success(monkeypatch):
    session_for(monkeypatch, persist, 0)
    with pytest.raises(persist.StalePatternWrite):
        await persist.update_match_patterns("123", {"pattern_ft_b": None}, expected_analyzed_at=None)


@pytest.mark.asyncio
async def test_older_analysis_upsert_is_rejected_without_retries(monkeypatch):
    session = session_for(monkeypatch, runner, 0)
    raw = MatchRawData(match_id="123", home_team="Home", away_team="Away", league_code="ENG PR")
    with pytest.raises(runner.StaleAnalysisWrite):
        await runner._upsert(analyze_match(raw), raw)
    session.execute.assert_awaited_once()
    sql = str(session.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "matches.deleted_at IS NULL" in sql
    assert "matches.analyzed_at <=" in sql


@pytest.mark.asyncio
async def test_changed_analysis_does_not_return_stale_backfill(monkeypatch):
    version = datetime(2026, 9, 14, tzinfo=timezone.utc)
    row = Match(match_id="123", home_team="Home", away_team="Away", ft_scores_1=[], analyzed_at=version)
    monkeypatch.setattr(api, "compute_all_patterns", AsyncMock(return_value={}))
    write = AsyncMock(side_effect=persist.StalePatternWrite("changed"))
    monkeypatch.setattr(api, "update_match_patterns", write)
    with pytest.raises(HTTPException) as error:
        await api._build_from_db(row)
    assert error.value.status_code == 409
    write.assert_awaited_once_with("123", {}, expected_analyzed_at=version)
