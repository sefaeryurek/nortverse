"""Skipped analyses avoid repeated scrapes and fixture page DB prewarming."""

from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.analysis import skip_cache
from app.api import services
from app.db.models import Match
from app.models import FixtureMatch, MatchRawData, SkipReason
from app.pipeline import runner


@pytest.mark.asyncio
async def test_saved_skip_is_a_small_upsert(monkeypatch):
    session = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(skip_cache, "get_session", fake_session)
    raw = MatchRawData(match_id="123", home_team="Home", away_team="Away", league_code="ENG PR")

    await skip_cache.save_skip(raw, SkipReason.H2H_INSUFFICIENT)

    stmt = session.execute.call_args.args[0]
    compiled = stmt.compile(dialect=postgresql.dialect())
    assert "ON CONFLICT (match_id) DO UPDATE" in str(compiled)
    assert "matches" not in str(compiled)
    assert "h2h_insufficient" in compiled.params.values()


@pytest.mark.asyncio
async def test_transient_fetch_failure_is_not_saved(monkeypatch):
    session = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(skip_cache, "get_session", fake_session)
    raw = MatchRawData(match_id="123", home_team="?", away_team="Away", league_code="ENG PR")

    await skip_cache.save_skip(raw, SkipReason.DATA_FETCH_FAILED)

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_recent_skip_query_has_expiration_cutoff(monkeypatch):
    session = AsyncMock()
    result = MagicMock()
    result.one_or_none.return_value = SimpleNamespace(
        match_id="123", home_team="Home", away_team="Away",
        league_code="ENG PR", reason="h2h_insufficient",
    )
    session.execute.return_value = result

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(skip_cache, "get_session", fake_session)

    snapshot = await skip_cache.get_recent_skip("123")

    assert snapshot is not None and snapshot.reason == "h2h_insufficient"
    stmt = session.execute.call_args.args[0]
    compiled = stmt.compile(dialect=postgresql.dialect())
    assert "skipped_analysis.checked_at >=" in str(compiled)
    assert any(isinstance(value, datetime) and value.tzinfo == timezone.utc
               for value in compiled.params.values())


@pytest.mark.asyncio
async def test_cached_skip_returns_without_scraping(monkeypatch):
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(services, "get_session", fake_session)
    monkeypatch.setattr(services, "analysis_cache", OrderedDict())
    monkeypatch.setattr(services, "_analysis_cached_at", {})
    monkeypatch.setattr(services, "get_recent_skip", AsyncMock(return_value=skip_cache.SkipSnapshot(
        "123", "Home", "Away", "ENG PR", "h2h_insufficient",
    )))
    scrape = AsyncMock()
    monkeypatch.setattr(services, "do_analyze", scrape)

    response = await services.analyze_and_cache("123")

    assert response.skipped and response.skip_reason == "h2h_insufficient"
    assert services.cache_get("123") is response
    scrape.assert_not_awaited()


@pytest.mark.asyncio
async def test_saved_cup_analysis_is_not_presented_as_league_evidence(monkeypatch):
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = Match(
        match_id="3086432", home_team="Home", away_team="Away",
        league_name="Netherlands KNVB Beker", league_code="Netherlands KNVB Beker",
        ft_scores_1=["1-0"],
    )
    session.execute.return_value = result

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(services, "get_session", fake_session)
    monkeypatch.setattr(services, "analysis_cache", OrderedDict())
    monkeypatch.setattr(services, "_analysis_cached_at", {})
    scrape = AsyncMock()
    monkeypatch.setattr(services, "do_analyze", scrape)

    response = await services.analyze_and_cache("3086432")
    assert response.skipped and response.skip_reason == "not_league_match"
    scrape.assert_not_awaited()


@pytest.mark.asyncio
async def test_fixture_competition_overrides_wrong_saved_league(monkeypatch):
    session = AsyncMock()
    saved = MagicMock()
    saved.scalar_one_or_none.return_value = Match(
        match_id="3086432", home_team="Home", away_team="Away",
        league_name="Dutch Eredivisie", league_code="NED D1", ft_scores_1=["1-0"],
    )
    bulletin = MagicMock()
    bulletin.scalar_one_or_none.return_value = {
        "match_id": "3086432", "home_team": "Home", "away_team": "Away",
        "league_name": "Netherlands KNVB Beker", "league_code": "Netherlands KNVB Beker",
    }
    session.execute.side_effect = [saved, bulletin]

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(services, "get_session", fake_session)
    monkeypatch.setattr(services, "analysis_cache", OrderedDict())
    monkeypatch.setattr(services, "_analysis_cached_at", {})
    scrape = AsyncMock()
    monkeypatch.setattr(services, "do_analyze", scrape)

    response = await services.analyze_and_cache("3086432")
    assert response.skipped and response.skip_reason == "not_league_match"
    scrape.assert_not_awaited()


@pytest.mark.asyncio
async def test_fixture_lookup_returns_only_one_json_item_and_bounds_known_date(monkeypatch):
    from datetime import datetime, timezone
    from sqlalchemy.dialects import postgresql

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = {
        "match_id": "3086432", "league_name": "Netherlands KNVB Beker",
    }
    session.execute.return_value = result

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(services, "get_session", fake_session)
    metadata = await services._fixture_metadata(
        "3086432", datetime(2026, 9, 22, 18, tzinfo=timezone.utc),
    )
    sql = str(session.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert metadata["league_name"] == "Netherlands KNVB Beker"
    assert "jsonb_path_query_first" in sql
    assert "fixture_cache.date IN" in sql


@pytest.mark.asyncio
async def test_new_filter_skip_is_saved(monkeypatch):
    raw = MatchRawData(match_id="123", home_team="Home", away_team="Away", league_code="ENG PR")
    monkeypatch.setattr(services, "fetch_match_detail", AsyncMock(return_value=raw))
    monkeypatch.setattr(services, "check_match_filters", lambda _raw: SimpleNamespace(
        passed=False, reason=SkipReason.H2H_INSUFFICIENT,
    ))
    save = AsyncMock()
    monkeypatch.setattr(services, "save_skip", save)

    response = await services.do_analyze("123")

    assert response.skipped and response.skip_reason == "h2h_insufficient"
    save.assert_awaited_once_with(raw, SkipReason.H2H_INSUFFICIENT)


@pytest.mark.asyncio
async def test_pipeline_saves_skipped_fixture_for_later_visits(monkeypatch):
    raw = MatchRawData(match_id="123", home_team="Home", away_team="Away", league_code="ENG PR")
    fixture = FixtureMatch(match_id="123", home_team="Home", away_team="Away", league_code="ENG PR")
    db_session = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield db_session

    @asynccontextmanager
    async def fake_browser():
        yield object()

    monkeypatch.setattr(runner, "get_session", fake_session)
    monkeypatch.setattr(runner, "browser_context", fake_browser)
    monkeypatch.setattr(runner, "fetch_istanbul_fixture", AsyncMock(return_value=[fixture]))
    monkeypatch.setattr(runner, "fetch_match_detail", AsyncMock(return_value=raw))
    monkeypatch.setattr(runner, "check_match_filters", lambda _raw: SimpleNamespace(
        passed=False, reason=SkipReason.H2H_INSUFFICIENT,
    ))
    save = AsyncMock()
    monkeypatch.setattr(runner, "save_skip", save)

    result = await runner.run_pipeline()

    assert result == {"analyzed": 0, "skipped": 1, "errors": 0}
    save.assert_awaited_once_with(raw, SkipReason.H2H_INSUFFICIENT)


@pytest.mark.asyncio
async def test_incremental_pipeline_avoids_prepared_and_cup_scrapes(monkeypatch):
    from datetime import timedelta

    kickoff = datetime.now(timezone.utc) + timedelta(days=1)
    league = FixtureMatch(match_id="123", home_team="Home", away_team="Away",
                          league_code="ENG PR", kickoff_time=kickoff)
    cup = FixtureMatch(match_id="456", home_team="Cup Home", away_team="Cup Away",
                       league_code="Netherlands KNVB Beker", kickoff_time=kickoff)

    @asynccontextmanager
    async def fake_browser():
        yield object()

    monkeypatch.setattr(runner, "browser_context", fake_browser)
    monkeypatch.setattr(runner, "fetch_istanbul_fixture", AsyncMock(return_value=[league, cup]))
    save = AsyncMock(return_value=1)
    monkeypatch.setattr(runner, "save_fixture_cache", save)
    prepared = AsyncMock(return_value={"123"})
    monkeypatch.setattr(runner, "_prepared_match_ids", prepared)
    scrape = AsyncMock()
    monkeypatch.setattr(runner, "fetch_match_detail", scrape)

    stats = await runner.run_pipeline(incremental=True)
    assert stats == {"analyzed": 0, "skipped": 1, "errors": 0}
    assert [fixture.match_id for fixture in save.await_args.args[1]] == ["123", "456"]
    prepared.assert_awaited_once_with(["123"])
    scrape.assert_not_awaited()
