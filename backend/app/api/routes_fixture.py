"""Fixture (bülten) endpoint'i."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.auth import is_admin_request
from app.config import ISTANBUL_TZ
from app.analysis.league_filter import is_main_league, is_shadow_league
from app.analysis.prematch_v4 import RULE_PARAMS
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


def pattern_status(b_data: dict | None, c_data: dict | None, d_data: dict | None) -> dict | None:
    """Bülten rozetleri: arşiv, maç öncesi kararın (v4) kullandığı eşiği geçiyorsa (≥10 maç) sayılır.

    Uyum: aktif arşivlerin MS kazananı (argmax) aynı mı. Hiç aktif arşiv yoksa None.
    """
    minimum = RULE_PARAMS["min_archive_matches"]
    active = {
        label: data for label, data in (("b", b_data), ("c", c_data), ("d", d_data))
        if isinstance(data, dict) and (data.get("match_count") or 0) >= minimum
    }
    if not active:
        return None
    winners = {
        label: max(["1", "x", "2"], key=lambda k, d=data: d.get(f"result_{k}_pct", 0))
        for label, data in active.items()
    }
    return {
        "has_b": "b" in active, "has_c": "c" in active, "has_d": "d" in active,
        "agreement": "b" in winners and "c" in winners and winners["b"] == winners["c"],
        "agreement_bcd": len(winners) == 3 and len(set(winners.values())) == 1,
    }


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


def _listed(league_name: str | None, league_code: str | None, shadow: bool) -> bool:
    """Bültende gösterilecek lig: 7 ana lig; `shadow` açıksa gölgedeki ligler de."""
    return is_main_league(league_name, league_code) or (shadow and is_shadow_league(league_name, league_code))


async def _bulletin_items(items: list[dict], req_date: date) -> list[FixtureMatchOut]:
    now = datetime.now(timezone.utc)
    today = now.astimezone(ISTANBUL_TZ).date()
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
            "shadow": is_shadow_league(match.league_name, match.league_code),
        }))
    return visible


@router.get("/api/fixture", response_model=list[FixtureMatchOut])
async def fixture(
    target_date: Optional[str] = Query(None, alias="date"),
    shadow: bool = Query(False, description="Gölgedeki ligleri de listele (deneme)"),
    request: Request = None,  # sonda: testler fixture(tarih) diye doğrudan çağırıyor
) -> list[FixtureMatchOut]:
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

    today = datetime.now(ISTANBUL_TZ).date()
    cache_key = parsed_date.isoformat() if parsed_date else today.isoformat()
    req_date = parsed_date or today

    max_past = today - timedelta(days=30)
    max_future = today + timedelta(days=14)
    if req_date < max_past or req_date > max_future:
        raise HTTPException(
            status_code=400,
            detail=f"Tarih sınırlar dışında. {max_past.isoformat()} ile {max_future.isoformat()} arası kabul edilir."
        )

    mem_key = f"{cache_key}:shadow" if shadow else cache_key

    # 1. Memory cache
    if mem_key in fixture_cache:
        ts, cached_result = fixture_cache[mem_key]
        if time.time() - ts < FIXTURE_CACHE_TTL:
            log.info("Fixture memory cache hit: %s", mem_key)
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
            for raw in db_row.matches_json:
                match = FixtureMatchOut(**raw)
                if not _listed(match.league_name, match.league_code, shadow):
                    continue
                if match.kickoff_time and datetime.fromisoformat(match.kickoff_time).astimezone(ISTANBUL_TZ).date() != req_date:
                    continue
                result.append(raw)
            fixture_cache_put(mem_key, result)
            log.info("Fixture DB cache hit: %s (%d lig maçı)", mem_key, len(result))
            return await _bulletin_items(result, req_date)
        except (ValueError, TypeError, AttributeError) as exc:
            log.warning("Fixture DB cache geçersiz, yeniden çekilecek [%s]: %s", cache_key, exc)

    # 3. Playwright scrape — sadece yönetici hesabı (diğer hesaplar kaynağa yük bindirmez)
    if not is_admin_request(request):
        raise HTTPException(503, "Bu günün bülteni henüz hazır değil")
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
    matches = [m for m in source_matches if _listed(m.league_name, m.league_code, shadow)]

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

    fixture_cache_put(mem_key, [m.model_dump() for m in result])
    return await _bulletin_items([m.model_dump() for m in result], req_date)


_pattern_status_cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()
_PATTERN_STATUS_TTL = 300.0
_PATTERN_STATUS_EMPTY_TTL = 30.0  # henüz pattern'i olmayan maç pipeline sonrası hızla güncellensin
_PATTERN_STATUS_MAX = 500


def _ps_cache_get(mid: str) -> dict | None:
    entry = _pattern_status_cache.get(mid)
    ttl = _PATTERN_STATUS_TTL if entry and entry[1] else _PATTERN_STATUS_EMPTY_TTL
    if entry and time.monotonic() - entry[0] < ttl:
        _pattern_status_cache.move_to_end(mid)
        return entry[1]
    return None


def _ps_cache_put(mid: str, val: dict) -> None:
    _pattern_status_cache[mid] = (time.monotonic(), val)
    _pattern_status_cache.move_to_end(mid)
    while len(_pattern_status_cache) > _PATTERN_STATUS_MAX:
        _pattern_status_cache.popitem(last=False)


@router.get("/api/fixture/pattern-status")
async def get_pattern_status(
    match_ids: str = Query(..., description="Virgülle ayrılmış match_id listesi"),
) -> dict[str, dict[str, bool]]:
    """Bülten maçlarının arşiv eşleşme durumunu toplu sorgular."""
    ids = [mid.strip() for mid in match_ids.split(",")
           if mid.strip() and re.fullmatch(r"\d{1,12}", mid.strip())]
    if not ids or len(ids) > 500:
        return {}

    result: dict[str, dict] = {}
    miss_ids: list[str] = []
    for mid in ids:
        cached = _ps_cache_get(mid)
        if cached is not None:
            if cached:
                result[mid] = cached
        else:
            miss_ids.append(mid)

    if miss_ids:
        async with get_session() as session:
            stmt = (
                select(
                    Match.match_id,
                    Match.pattern_ft_b,
                    Match.pattern_ft_c,
                    Match.pattern_ft_d,
                )
                .where(Match.match_id.in_(miss_ids))
                .where(Match.deleted_at.is_(None))
            )
            rows = (await session.execute(stmt)).all()

        found_ids: set[str] = set()
        for row in rows:
            found_ids.add(row[0])
            b_data = row[1]
            c_data = row[2]
            d_data = row[3]
            val = pattern_status(b_data, c_data, d_data)
            if val is not None:
                _ps_cache_put(row[0], val)
                result[row[0]] = val
            else:
                _ps_cache_put(row[0], {})

        for mid in miss_ids:
            if mid not in found_ids:
                _ps_cache_put(mid, {})

    return result
