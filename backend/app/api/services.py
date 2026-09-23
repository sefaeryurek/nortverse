"""API iş mantığı: cache, analiz, arka plan kuyruğu.

Route modülleri bu modülden ortak state ve yardımcıları import eder.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Optional
from weakref import WeakValueDictionary

from fastapi import HTTPException
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import JSONB, JSONPATH, insert

from app.api.schemas import AnalyzeResponse, PeriodOut
from app.analysis import analyze_match, check_match_filters
from app.analysis.league_filter import is_supported_league
from app.analysis.pattern_stats import PatternResult
from app.analysis.league_filter import canonical_league_name
from app.analysis.snapshots import RULE_VERSION, prekickoff_picks
from app.analysis.persist import (
    StalePatternWrite,
    compute_all_patterns,
    update_match_patterns,
)
from app.analysis.skip_cache import get_recent_skip, save_skip
from app.analysis.trends import TrendsData, compute_trends
from app.db.connection import get_session
from app.db.models import AnalysisSnapshot, FixtureCache, Match
from app.scraper import fetch_match_detail

log = logging.getLogger(__name__)

# ─── Sabitler ────────────────────────────────────────────────────────────────

_CACHE_MAX = 500
ANALYSIS_CACHE_TTL = 600.0
SNAPSHOT_POLL_TTL = 15.0
ANALYSIS_TIMEOUT = 90.0
FIXTURE_CACHE_TTL = 600.0

# ─── Cache & eşzamanlılık ────────────────────────────────────────────────────

_analysis_cached_at: dict[str, float] = {}
analysis_cache: OrderedDict[str, AnalyzeResponse] = OrderedDict()
_analysis_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
_snapshot_checked_at: dict[str, float] = {}
_snapshot_finalized: set[str] = set()

fixture_cache: dict[str, tuple[float, list]] = {}

bg_queue: asyncio.Queue[str] | None = None
_bg_queued: set[str] = set()


def cache_put(match_id: str, value: AnalyzeResponse) -> None:
    """LRU semantiği: ekle, en sona taşı, sınırı aşarsa en eskiyi at."""
    analysis_cache[match_id] = value
    _analysis_cached_at[match_id] = time.monotonic()
    analysis_cache.move_to_end(match_id)
    while len(analysis_cache) > _CACHE_MAX:
        evicted, _ = analysis_cache.popitem(last=False)
        _analysis_cached_at.pop(evicted, None)
        _snapshot_checked_at.pop(evicted, None)
        _snapshot_finalized.discard(evicted)


def cache_get(match_id: str) -> AnalyzeResponse | None:
    if match_id not in analysis_cache:
        return None
    cached_at = _analysis_cached_at.get(match_id)
    if cached_at is None or time.monotonic() - cached_at >= ANALYSIS_CACHE_TTL:
        analysis_cache.pop(match_id, None)
        _analysis_cached_at.pop(match_id, None)
        return None
    analysis_cache.move_to_end(match_id)
    return analysis_cache[match_id]


def get_or_make_lock(match_id: str) -> asyncio.Lock:
    """İşlem ve bekleyenleri yaşadığı sürece aynı lock'u döndür."""
    lock = _analysis_locks.get(match_id)
    if lock is None:
        lock = asyncio.Lock()
        _analysis_locks[match_id] = lock
    return lock


async def _fixture_metadata(match_id: str, kickoff_time: datetime | None = None) -> dict | None:
    """Use the source bulletin competition when detail HTML inferred the wrong league."""
    try:
        value = cast(func.jsonb_path_query_first(
            FixtureCache.matches_json,
            cast('$[*] ? (@.match_id == $id)', JSONPATH),
            func.jsonb_build_object("id", match_id),
        ), JSONB)
        query = select(value).where(
            FixtureCache.matches_json.contains([{"match_id": match_id}]),
        )
        if kickoff_time is not None and kickoff_time.tzinfo is not None:
            day = kickoff_time.astimezone(timezone(timedelta(hours=3))).date()
            query = query.where(FixtureCache.date.in_([
                (day + timedelta(days=offset)).isoformat() for offset in (-1, 0, 1)
            ]))
        async with get_session() as session:
            payload = (await session.execute(
                query.order_by(FixtureCache.date.desc()).limit(1)
            )).scalar_one_or_none()
    except Exception as exc:
        log.warning("Bülten lig bilgisi okunamadı [%s]: %s", match_id, exc)
        return None
    return payload if isinstance(payload, dict) and payload.get("match_id") == match_id else None


# ─── DB-first yardımcıları ───────────────────────────────────────────────────

def _pat(blob: dict | None) -> Optional[PatternResult]:
    """JSONB → PatternResult; None ise None döner."""
    if not blob:
        return None
    try:
        return PatternResult.model_validate(blob)
    except Exception as exc:
        log.warning("Saklı pattern parse edilemedi: %s", exc)
        return None


def _trends_parse(blob: dict | None) -> Optional[TrendsData]:
    """JSONB → TrendsData; None ise None döner."""
    if not blob:
        return None
    try:
        return TrendsData.model_validate(blob)
    except Exception as exc:
        log.warning("Saklı trends parse edilemedi: %s", exc)
        return None


async def _frozen_recommendations(row: Match, patterns: dict[str, dict | None]) -> list[dict]:
    """Read the immutable snapshot, creating it only while the match is upcoming."""
    async with get_session() as session:
        snapshot = await session.get(AnalysisSnapshot, (row.match_id, RULE_VERSION))
        if snapshot is not None:
            _snapshot_finalized.add(row.match_id)
            return snapshot.picks if isinstance(snapshot.picks, list) else []
        if row.analyzed_at is None:
            return []
        captured_at = datetime.now(timezone.utc)
        current = (await session.execute(
            select(Match).where(
                Match.match_id == row.match_id,
                Match.deleted_at.is_(None),
                Match.analyzed_at == row.analyzed_at,
                Match.kickoff_time == row.kickoff_time,
                Match.kickoff_time > captured_at,
            ).with_for_update()
        )).scalar_one_or_none()
        if current is None:
            return []
        picks = prekickoff_picks(
            analyzed_at=current.analyzed_at, captured_at=captured_at,
            kickoff_time=current.kickoff_time, league_name=current.league_name,
            league_code=current.league_code, patterns=patterns,
        )
        if picks is None:
            return []
        written = await session.execute(
            insert(AnalysisSnapshot).values(
                match_id=row.match_id, rule_version=RULE_VERSION,
                captured_at=captured_at, analyzed_at=current.analyzed_at,
                kickoff_time=current.kickoff_time,
                league_name=(current.league_name
                             or canonical_league_name(current.league_code)
                             or current.league_code
                             or "unknown"),
                picks=picks,
            ).on_conflict_do_nothing(index_elements=["match_id", "rule_version"])
        )
        if written.rowcount == 1:
            _snapshot_finalized.add(row.match_id)
            return picks
        snapshot = await session.get(AnalysisSnapshot, (row.match_id, RULE_VERSION))
        if snapshot is not None:
            _snapshot_finalized.add(row.match_id)
    return snapshot.picks if snapshot and isinstance(snapshot.picks, list) else []


async def _refresh_cached_recommendations(response: AnalyzeResponse) -> AnalyzeResponse:
    """Keep the fast analysis cache while reading externally written snapshots fresh."""
    if not isinstance(response, AnalyzeResponse):
        return response
    if response.skipped:
        return response
    match_id = response.match_id
    if match_id in _snapshot_finalized or response.ft_recommendations:
        return response
    now = time.monotonic()
    if now - _snapshot_checked_at.get(match_id, 0.0) < SNAPSHOT_POLL_TTL:
        return response
    _snapshot_checked_at[match_id] = now
    try:
        async with get_session() as session:
            snapshot = await session.get(
                AnalysisSnapshot, (match_id, RULE_VERSION),
            )
    except Exception as exc:
        log.warning("Snapshot cache yenilemesi başarısız [%s]: %s", response.match_id, exc)
        return response
    if snapshot is not None:
        _snapshot_finalized.add(match_id)
    picks = snapshot.picks if snapshot and isinstance(snapshot.picks, list) else []
    if [item.model_dump() for item in response.ft_recommendations] == picks:
        return response
    refreshed = AnalyzeResponse.model_validate({
        **response.model_dump(), "ft_recommendations": picks,
    })
    cache_put(match_id, refreshed)
    return refreshed


async def build_from_db(row: Match) -> AnalyzeResponse | None:
    """DB satırından AnalyzeResponse üret.

    HIZLI YOL: pattern hesabı tamamlandıysa (eşleşme bulunmasa bile) deserialize.
    YAVAŞ YOL: hesaplama durumu bilinmiyorsa hesapla ve durumu DB'ye kaydet.
    """
    if row.ft_scores_1 is None:
        return None

    ht_s1 = row.ht_scores_1 or []
    ht_sx = row.ht_scores_x or []
    ht_s2 = row.ht_scores_2 or []
    h2_s1 = row.h2_scores_1 or []
    h2_sx = row.h2_scores_x or []
    h2_s2 = row.h2_scores_2 or []
    ft_s1 = row.ft_scores_1 or []
    ft_sx = row.ft_scores_x or []
    ft_s2 = row.ft_scores_2 or []
    ft_ratios = row.ft_all_ratios or {}
    mid = row.match_id

    if row.pattern_computed_at is not None:
        log.debug("Hızlı yol — saklı pattern'ler kullanıldı: %s", mid)
        ht_b, ht_c = _pat(row.pattern_ht_b), _pat(row.pattern_ht_c)
        h2_b, h2_c = _pat(row.pattern_h2_b), _pat(row.pattern_h2_c)
        ft_b, ft_c = _pat(row.pattern_ft_b), _pat(row.pattern_ft_c)
        patterns = {
            "pattern_ht_b": row.pattern_ht_b, "pattern_ht_c": row.pattern_ht_c,
            "pattern_h2_b": row.pattern_h2_b, "pattern_h2_c": row.pattern_h2_c,
            "pattern_ft_b": row.pattern_ft_b, "pattern_ft_c": row.pattern_ft_c,
        }
    else:
        log.info("Yavaş yol — pattern durumu bilinmiyor, hesaplanıyor: %s", mid)
        patterns = await compute_all_patterns(
            match_id=mid,
            ht_scores=(ht_s1, ht_sx, ht_s2),
            h2_scores=(h2_s1, h2_sx, h2_s2),
            ft_scores=(ft_s1, ft_sx, ft_s2),
            ft_ratios=ft_ratios,
            as_of=row.analyzed_at,
        )
        try:
            await update_match_patterns(mid, patterns, expected_analyzed_at=row.analyzed_at)
        except StalePatternWrite:
            raise HTTPException(409, "Analiz bu sırada güncellendi. Lütfen yeniden deneyin.")
        except Exception:
            log.warning("Lazy backfill kaydedilemedi [%s]; hesaplanan yanıt kullanılacak", mid)

        ht_b, ht_c = _pat(patterns["pattern_ht_b"]), _pat(patterns["pattern_ht_c"])
        h2_b, h2_c = _pat(patterns["pattern_h2_b"]), _pat(patterns["pattern_h2_c"])
        ft_b, ft_c = _pat(patterns["pattern_ft_b"]), _pat(patterns["pattern_ft_c"])

    recommendations = await _frozen_recommendations(row, patterns)
    return AnalyzeResponse(
        match_id=row.match_id,
        home_team=row.home_team,
        away_team=row.away_team,
        league_code=row.league_code or "",
        season=row.season or "",
        ht=PeriodOut(scores_1=ht_s1, scores_x=ht_sx, scores_2=ht_s2),
        half2=PeriodOut(scores_1=h2_s1, scores_x=h2_sx, scores_2=h2_s2),
        ft=PeriodOut(scores_1=ft_s1, scores_x=ft_sx, scores_2=ft_s2),
        ht_b=ht_b, ht_c=ht_c,
        h2_b=h2_b, h2_c=h2_c,
        ft_b=ft_b, ft_c=ft_c,
        trends=_trends_parse(row.trends),
        recommendation_rule_version=RULE_VERSION,
        ft_recommendations=recommendations,
    )


# ─── Analiz orchestration ───────────────────────────────────────────────────

async def _analyze_db_only(match_id: str) -> bool:
    async with get_or_make_lock(match_id):
        return await _analyze_db_only_locked(match_id)


async def _analyze_db_only_locked(match_id: str) -> bool:
    """Sadece DB hit denemesi — Playwright YOK."""
    if cache_get(match_id) is not None:
        return True
    try:
        async with get_session() as session:
            row = (await session.execute(
                select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
            )).scalar_one_or_none()
        if row is None:
            return False
        response = await build_from_db(row)
        if response is None:
            return False
        cache_put(match_id, response)
        return True
    except Exception as exc:
        log.warning("DB-only analiz başarısız [%s]: %s", match_id, exc)
        return False


async def analyze_and_cache(match_id: str) -> AnalyzeResponse:
    """DB kontrol et → bulursa B/C hesapla (hızlı). Yoksa Playwright scrape (yavaş)."""
    cached = cache_get(match_id)
    if cached is not None:
        return await _refresh_cached_recommendations(cached)
    lock = get_or_make_lock(match_id)
    async with lock:
        cached = cache_get(match_id)
        if cached is not None:
            return await _refresh_cached_recommendations(cached)

        db_row = None
        try:
            async with get_session() as session:
                db_row = (
                    await session.execute(
                        select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
                    )
                ).scalar_one_or_none()
        except Exception as exc:
            log.warning("Analiz DB okunamadı [%s]: %s", match_id, exc)

        fixture = await _fixture_metadata(match_id, db_row.kickoff_time if db_row else None)
        if fixture is not None and not is_supported_league(fixture.get("league_name"), fixture.get("league_code")):
            response = AnalyzeResponse(
                match_id=match_id,
                home_team=fixture.get("home_team") or (db_row.home_team if db_row else ""),
                away_team=fixture.get("away_team") or (db_row.away_team if db_row else ""),
                league_code=fixture.get("league_code") or "",
                season="",
                ht=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
                half2=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
                ft=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
                skipped=True,
                skip_reason="not_league_match",
            )
            cache_put(match_id, response)
            return response

        if db_row is not None:
            if not is_supported_league(db_row.league_name, db_row.league_code):
                response = AnalyzeResponse(
                    match_id=match_id,
                    home_team=db_row.home_team,
                    away_team=db_row.away_team,
                    league_code=db_row.league_code or "",
                    season="",
                    ht=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
                    half2=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
                    ft=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
                    skipped=True,
                    skip_reason="not_league_match",
                )
                cache_put(match_id, response)
                return response
            response = await build_from_db(db_row)
            if response is not None:
                log.info("DB hit — anlık: %s", match_id)
                cache_put(match_id, response)
                return response

        try:
            skipped = await get_recent_skip(match_id)
        except Exception as exc:
            log.warning("Atlanmış analiz önbelleği okunamadı [%s]: %s", match_id, exc)
            skipped = None
        if skipped is not None:
            response = AnalyzeResponse(
                match_id=skipped.match_id,
                home_team=skipped.home_team,
                away_team=skipped.away_team,
                league_code=skipped.league_code,
                season="",
                ht=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
                half2=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
                ft=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
                skipped=True,
                skip_reason=skipped.reason,
            )
            cache_put(match_id, response)
            return response

        log.info("DB miss — Playwright scrape: %s", match_id)
        response = await do_analyze(match_id)
        cache_put(match_id, response)
        return response


async def do_analyze(match_id: str) -> AnalyzeResponse:
    """Playwright ile scrape + analiz + DB'ye kaydet."""
    raw = await fetch_match_detail(match_id)
    check = check_match_filters(raw)

    if not check.passed:
        if check.reason is not None:
            try:
                await save_skip(raw, check.reason)
            except Exception as exc:
                log.warning("Atlanmış analiz kaydedilemedi [%s]: %s", match_id, exc)
        return AnalyzeResponse(
            match_id=match_id,
            home_team=raw.home_team,
            away_team=raw.away_team,
            league_code=raw.league_code or "",
            season="",
            ht=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
            half2=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
            ft=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
            skipped=True,
            skip_reason=check.reason.value if check.reason else None,
        )

    result = analyze_match(raw)
    patterns = await compute_all_patterns(
        match_id=match_id,
        ht_scores=(result.ht.scores_1, result.ht.scores_x, result.ht.scores_2),
        h2_scores=(result.half2.scores_1, result.half2.scores_x, result.half2.scores_2),
        ft_scores=(result.ft.scores_1, result.ft.scores_x, result.ft.scores_2),
        ft_ratios=result.ft.all_ratios,
        as_of=result.analyzed_at,
    )

    frozen_recommendations: list[dict] = []
    try:
        from app.pipeline.runner import StaleAnalysisWrite, _upsert as _persist_full
        frozen_recommendations = await _persist_full(result, raw, patterns)
    except StaleAnalysisWrite:
        raise HTTPException(409, "Daha güncel bir analiz var. Lütfen yeniden deneyin.")
    except Exception as exc:
        log.error(
            "Maç DB'ye kaydedilemedi (sonraki ziyarette tekrar Playwright açılacak) [%s]: %s",
            match_id, exc, exc_info=True,
        )

    try:
        trends_data: Optional[TrendsData] = compute_trends(raw)
    except Exception as exc:
        log.warning("Trends hesaplanamadı [%s]: %s", match_id, exc)
        trends_data = None

    return AnalyzeResponse(
        match_id=result.match_id,
        home_team=result.home_team,
        away_team=result.away_team,
        league_code=result.league_code,
        season=result.season,
        ht=PeriodOut(scores_1=result.ht.scores_1, scores_x=result.ht.scores_x, scores_2=result.ht.scores_2),
        half2=PeriodOut(scores_1=result.half2.scores_1, scores_x=result.half2.scores_x, scores_2=result.half2.scores_2),
        ft=PeriodOut(scores_1=result.ft.scores_1, scores_x=result.ft.scores_x, scores_2=result.ft.scores_2),
        ht_b=_pat(patterns["pattern_ht_b"]), ht_c=_pat(patterns["pattern_ht_c"]),
        h2_b=_pat(patterns["pattern_h2_b"]), h2_c=_pat(patterns["pattern_h2_c"]),
        ft_b=_pat(patterns["pattern_ft_b"]), ft_c=_pat(patterns["pattern_ft_c"]),
        trends=trends_data,
        recommendation_rule_version=RULE_VERSION,
        ft_recommendations=frozen_recommendations,
    )


# ─── Arka plan kuyruğu ───────────────────────────────────────────────────────

def init_bg_queue() -> None:
    global bg_queue
    bg_queue = asyncio.Queue()


def shutdown_bg_queue() -> None:
    global bg_queue
    _bg_queued.clear()
    bg_queue = None


async def bg_worker() -> None:
    """Bülten yüklenince DB'de hazır olan maçların cache'ini ısıtır.

    KRİTİK: Sadece DB-hit dener; Playwright AÇMAZ.
    """
    assert bg_queue is not None
    while True:
        match_id = await bg_queue.get()
        try:
            ok = await _analyze_db_only(match_id)
            if ok:
                log.info("Arka plan DB-cache hazırlandı: %s", match_id)
            else:
                log.debug("Arka plan: DB'de yok, atlandı (foreground tetikleyecek): %s", match_id)
        except Exception as exc:
            log.warning("Arka plan DB-cache hatası [%s]: %s", match_id, exc)
        finally:
            _bg_queued.discard(match_id)
            bg_queue.task_done()


def enqueue_bg_analysis(matches: list) -> None:
    """Arka plan analiz kuyruğuna maçları ekler."""
    if bg_queue is None:
        return
    for m in matches:
        if cache_get(m.match_id) is None and m.match_id not in _bg_queued:
            _bg_queued.add(m.match_id)
            bg_queue.put_nowait(m.match_id)
    log.info("Arka plan kuyruğu: %d bekleyen maç", bg_queue.qsize())
