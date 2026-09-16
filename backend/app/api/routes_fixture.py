"""Fixture (bülten) endpoint'i."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.analysis.league_filter import is_supported_league
from app.api.schemas import FixtureMatchOut
from app.api.services import (
    FIXTURE_CACHE_TTL,
    enqueue_bg_analysis,
    fixture_cache,
)
from app.db.connection import get_session
from app.db.models import FixtureCache
from app.scraper import fetch_fixture

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/fixture", response_model=list[FixtureMatchOut])
async def fixture(target_date: Optional[str] = Query(None, alias="date")) -> list[FixtureMatchOut]:
    """Günlük Hot maçları döndürür.

    3 katmanlı cache:
    1. Memory cache (10 dk TTL)
    2. DB cache (kalıcı / bugün 1 saat)
    3. Playwright scrape
    """
    parsed_date: Optional[date] = None
    if target_date:
        try:
            parsed_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. Kullanım: YYYY-MM-DD")

    today = datetime.now(timezone(timedelta(hours=3))).date()
    cache_key = parsed_date.isoformat() if parsed_date else today.isoformat()
    req_date = parsed_date or today

    max_past = today - timedelta(days=30)
    max_future = today + timedelta(days=14)
    if req_date < max_past or req_date > max_future:
        raise HTTPException(
            status_code=400,
            detail=f"Tarih sınırlar dışında. {max_past.isoformat()} ile {max_future.isoformat()} arası kabul edilir."
        )

    # 1. Memory cache
    if cache_key in fixture_cache:
        ts, cached_result = fixture_cache[cache_key]
        if time.time() - ts < FIXTURE_CACHE_TTL:
            log.info("Fixture memory cache hit: %s", cache_key)
            return cached_result

    # 2. DB cache
    db_row = None
    try:
        async with get_session() as session:
            db_row = await session.get(FixtureCache, cache_key)
    except Exception as exc:
        log.warning("Fixture DB cache okunamadı (migration uygulanmamış olabilir): %s", exc)

    if db_row is not None:
        try:
            cached_at = db_row.cached_at
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            is_stale = age < 0 or (req_date >= today and age >= 3600)
            if not is_stale:
                if not isinstance(db_row.matches_json, list):
                    raise ValueError("Fixture cache must contain a list")
                result = [FixtureMatchOut(**m) for m in db_row.matches_json]
                result = [m for m in result if is_supported_league(m.league_name, m.league_code)]
                fixture_cache[cache_key] = (time.time(), result)
                log.info("Fixture DB cache hit: %s (%.0f sn önce, %d lig maçı)",
                         cache_key, age, len(result))
                enqueue_bg_analysis(result)
                return result
        except (ValueError, TypeError, AttributeError) as exc:
            log.warning("Fixture DB cache geçersiz, yeniden çekilecek [%s]: %s", cache_key, exc)

    # 3. Playwright scrape
    log.info("Fixture Playwright scrape başlıyor: %s", cache_key)
    try:
        matches = await asyncio.wait_for(
            fetch_fixture(target_date=parsed_date, only_hot=True),
            timeout=20.0,
        )
    except asyncio.TimeoutError:
        log.error("Fixture scrape 20sn içinde dönmedi: %s", cache_key)
        raise HTTPException(
            status_code=503,
            detail="Maç verisi çekilemedi (timeout). Lütfen birkaç dakika sonra tekrar deneyin.",
        )
    matches = [m for m in matches if is_supported_league(m.league_name, m.league_code)]

    result = [
        FixtureMatchOut(
            match_id=m.match_id,
            home_team=m.home_team,
            away_team=m.away_team,
            league_code=m.league_code,
            league_name=m.league_name,
            kickoff_time=m.kickoff_time.isoformat() if m.kickoff_time else None,
        )
        for m in matches
    ]

    # DB'ye kaydet
    try:
        async with get_session() as session:
            row = FixtureCache(
                date=cache_key,
                matches_json=[m.model_dump() for m in result],
                cached_at=datetime.now(timezone.utc),
            )
            await session.merge(row)
        log.info("Fixture DB'ye kaydedildi: %s (%d maç)", cache_key, len(result))
    except Exception as exc:
        log.warning("Fixture DB'ye kaydedilemedi: %s", exc)

    fixture_cache[cache_key] = (time.time(), result)
    enqueue_bg_analysis(result)
    return result
