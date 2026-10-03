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
from app.api.live_snapshot import get_live_snapshot
from app.api.score_state import _utc, resolve_match_state
from app.api.services import (
    FIXTURE_CACHE_TTL,
    fixture_cache,
    fixture_cache_put,
)
from sqlalchemy import select

from app.db.connection import get_session
from app.db.models import FixtureCache, Match
from app.pipeline.runner import save_fixture_cache
from app.scraper import fetch_istanbul_fixture

log = logging.getLogger(__name__)
router = APIRouter()


async def _enrich_prediction_status(items: list[dict]) -> dict[str, bool]:
    """Match ID'leri için DB'de analiz verisi olup olmadığını toplu sorgular."""
    ids = [it.get("match_id", "") for it in items]
    ids = [mid for mid in ids if mid]
    if not ids:
        return {}

    result: dict[str, bool] = {}
    try:
        async with get_session() as session:
            stmt = (
                select(Match.match_id)
                .where(Match.match_id.in_(ids))
                .where(Match.deleted_at.is_(None))
                .where(Match.ft_scores_1.isnot(None))
            )
            rows = (await session.execute(stmt)).scalars().all()
            for mid in rows:
                result[mid] = True
    except Exception as exc:
        log.warning("Prediction status sorgusu başarısız: %s", exc)

    return result


async def _bulletin_items(items: list[dict], req_date: date) -> list[FixtureMatchOut]:
    now = datetime.now(timezone.utc)
    today = now.astimezone(timezone(timedelta(hours=3))).date()
    live_snapshot = await get_live_snapshot() if today - timedelta(days=1) <= req_date <= today else None

    pred_status = await _enrich_prediction_status(items)

    visible: list[FixtureMatchOut] = []
    for item in items:
        match = FixtureMatchOut(**item)
        kickoff = _utc(match.kickoff_time)
        observed = live_snapshot.scores.get(match.match_id) if live_snapshot else None
        state = resolve_match_state(
            item, kickoff, None, None,
            observed, live_snapshot.checked_at if live_snapshot else None, now,
        )
        if state.status not in ("scheduled", "live"):
            continue
        if state.status == "scheduled" and (
            (kickoff is not None and kickoff <= now)
            or (kickoff is None and req_date < today)
        ):
            continue
        visible.append(match.model_copy(update={
            "status": state.status,
            "live_home": state.live_home,
            "live_away": state.live_away,
            "live_minute": state.live_minute,
            "score_checked_at": state.score_checked_at,
            "has_prediction": pred_status.get(match.match_id, False),
        }))
    return visible


@router.get("/api/fixture", response_model=list[FixtureMatchOut])
async def fixture(target_date: Optional[str] = Query(None, alias="date")) -> list[FixtureMatchOut]:
    """Günlük Hot maçları döndürür.

    3 katmanlı cache:
    1. Memory cache (10 dk TTL)
    2. DB cache (günlük pipeline tarafından güncellenir)
    3. Yalnızca cache yoksa Playwright scrape
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
            return await _bulletin_items(cached_result, req_date)

    # 2. DB cache
    db_row = None
    try:
        async with get_session() as session:
            db_row = await session.get(FixtureCache, cache_key)
    except Exception as exc:
        log.warning("Fixture DB cache okunamadı (migration uygulanmamış olabilir): %s", exc)

    if db_row is not None:
        try:
            # Bugünkü bülteni günlük pipeline zaten yeniliyor. Bir saatlik yaş sınırı,
            # her cache miss'te 20 sn Playwright bekletip sonunda 503 üretiyordu.
            if not isinstance(db_row.matches_json, list):
                raise ValueError("Fixture cache must contain a list")
            result = []
            istanbul_tz = timezone(timedelta(hours=3))
            for raw in db_row.matches_json:
                match = FixtureMatchOut(**raw)
                if not is_supported_league(match.league_name, match.league_code):
                    continue
                if match.kickoff_time and datetime.fromisoformat(match.kickoff_time).astimezone(istanbul_tz).date() != req_date:
                    continue
                result.append(raw)
            fixture_cache_put(cache_key, result)
            log.info("Fixture DB cache hit: %s (%d lig maçı)", cache_key, len(result))
            return await _bulletin_items(result, req_date)
        except (ValueError, TypeError, AttributeError) as exc:
            log.warning("Fixture DB cache geçersiz, yeniden çekilecek [%s]: %s", cache_key, exc)

    # 3. Playwright scrape
    log.info("Fixture Playwright scrape başlıyor: %s", cache_key)
    try:
        matches = await asyncio.wait_for(
            fetch_istanbul_fixture(req_date, only_hot=False),
            timeout=45.0,
        )
    except asyncio.TimeoutError:
        log.error("Fixture scrape 45sn içinde dönmedi: %s", cache_key)
        raise HTTPException(
            status_code=503,
            detail="Maç verisi çekilemedi (timeout). Lütfen birkaç dakika sonra tekrar deneyin.",
        )
    except Exception as exc:
        log.exception("Fixture scrape başarısız: %s", cache_key)
        raise HTTPException(
            status_code=503,
            detail="Maç verisi şu anda alınamıyor. Lütfen biraz sonra tekrar deneyin.",
        ) from exc
    source_matches = matches
    matches = [m for m in source_matches if is_supported_league(m.league_name, m.league_code)]

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
        await save_fixture_cache(req_date, source_matches)
        log.info("Fixture DB'ye kaydedildi: %s (%d kaynak maçı)", cache_key, len(source_matches))
    except Exception as exc:
        log.warning("Fixture DB'ye kaydedilemedi: %s", exc)

    fixture_cache_put(cache_key, [m.model_dump() for m in result])
    return await _bulletin_items([m.model_dump() for m in result], req_date)


@router.get("/api/fixture/pattern-status")
async def get_pattern_status(
    match_ids: str = Query(..., description="Virgülle ayrılmış match_id listesi"),
) -> dict[str, dict[str, bool]]:
    """Bülten maçlarının arşiv eşleşme durumunu toplu sorgular."""
    ids = [mid.strip() for mid in match_ids.split(",") if mid.strip()]
    if not ids or len(ids) > 500:
        return {}

    async with get_session() as session:
        stmt = (
            select(
                Match.match_id,
                Match.pattern_ft_b,
                Match.pattern_ft_c,
                Match.pattern_ft_d,
            )
            .where(Match.match_id.in_(ids))
            .where(Match.deleted_at.is_(None))
        )
        rows = (await session.execute(stmt)).all()

    result: dict[str, dict] = {}
    for row in rows:
        b_data = row[1]
        c_data = row[2]
        d_data = row[3]
        has_b = bool(b_data and isinstance(b_data, dict) and b_data.get("match_count", 0) >= 5)
        has_c = bool(c_data and isinstance(c_data, dict) and c_data.get("match_count", 0) >= 1)
        has_d = bool(d_data and isinstance(d_data, dict) and d_data.get("match_count", 0) >= 1)
        if has_b or has_c or has_d:
            agreement = False
            if has_b and has_c:
                b_winner = max(
                    ["1", "x", "2"],
                    key=lambda k: b_data.get(f"result_{k}_pct", 0),
                )
                c_winner = max(
                    ["1", "x", "2"],
                    key=lambda k: c_data.get(f"result_{k}_pct", 0),
                )
                agreement = b_winner == c_winner
            result[row[0]] = {"has_b": has_b, "has_c": has_c, "has_d": has_d, "agreement": agreement}
    return result
