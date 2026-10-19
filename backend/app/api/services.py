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
from sqlalchemy.dialects.postgresql import JSONB, JSONPATH

from app.config import ISTANBUL_TZ
from app.api.schemas import AnalyzeResponse, PeriodOut, RecommendationOut
from app.analysis import analyze_match, check_match_filters
from app.analysis.league_filter import is_supported_league, match_league_name
from app.analysis.pattern_stats import PatternResult
from app.analysis.prematch_v5 import V5_RULE_VERSION as RULE_VERSION
from app.analysis.prematch_v5 import capture_recommendations


from app.analysis.persist import (
    FAMILIES,
    StalePatternWrite,
    compute_all_patterns,
    hash_string,
    pattern_as_of,
    pattern_hashes,
    pattern_keys,
    stale_families,
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
_snapshot_finalized: OrderedDict[str, float] = OrderedDict()

_SNAPSHOT_FINALIZED_MAX = 600


def _snapshot_finalized_put(key: str) -> None:
    _snapshot_finalized[key] = time.monotonic()
    _snapshot_finalized.move_to_end(key)
    while len(_snapshot_finalized) > _SNAPSHOT_FINALIZED_MAX:
        _snapshot_finalized.popitem(last=False)


fixture_cache: OrderedDict[str, tuple[float, list]] = OrderedDict()
_FIXTURE_CACHE_MAX = 30


def fixture_cache_put(key: str, data: list) -> None:
    """Fixture cache'e yaz, sınırı aşarsa en eski entry'yi at."""
    fixture_cache[key] = (time.time(), data)
    fixture_cache.move_to_end(key)
    while len(fixture_cache) > _FIXTURE_CACHE_MAX:
        fixture_cache.popitem(last=False)

bg_queue: asyncio.Queue[str] | None = None
_bg_queued: set[str] = set()
_BG_QUEUED_MAX = 500


def _snapshot_cache_key(match_id: str) -> str:
    return f"{RULE_VERSION}:{match_id}"


def cache_put(match_id: str, value: AnalyzeResponse) -> None:
    """LRU semantiği: ekle, en sona taşı, sınırı aşarsa en eskiyi at."""
    analysis_cache[match_id] = value
    _analysis_cached_at[match_id] = time.monotonic()
    analysis_cache.move_to_end(match_id)
    while len(analysis_cache) > _CACHE_MAX:
        evicted, _ = analysis_cache.popitem(last=False)
        _analysis_cached_at.pop(evicted, None)
        snapshot_key = _snapshot_cache_key(evicted)
        _snapshot_checked_at.pop(snapshot_key, None)
        _snapshot_finalized.pop(snapshot_key, None)


def cache_get(match_id: str) -> AnalyzeResponse | None:
    if match_id not in analysis_cache:
        return None
    cached_at = _analysis_cached_at.get(match_id)
    if cached_at is None or time.monotonic() - cached_at >= ANALYSIS_CACHE_TTL:
        analysis_cache.pop(match_id, None)
        _analysis_cached_at.pop(match_id, None)
        snapshot_key = _snapshot_cache_key(match_id)
        _snapshot_checked_at.pop(snapshot_key, None)
        _snapshot_finalized.pop(snapshot_key, None)
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
            day = kickoff_time.astimezone(ISTANBUL_TZ).date()
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


async def _legacy_v4_picks(session, match_id: str) -> list[dict]:
    """v5'ten önce dondurulmuş ve artık başlamış maçlar: o gün gösterilen v4 seçimi (geçmiş kaybolmasın)."""
    from app.analysis.prematch_v4 import LEGACY_V4_RULE_VERSIONS

    for version in LEGACY_V4_RULE_VERSIONS:
        snapshot = await session.get(AnalysisSnapshot, (match_id, version))
        if snapshot is not None and isinstance(snapshot.picks, list):
            return snapshot.picks
    return []


async def _frozen_recommendations(row: Match, patterns: dict[str, dict | None],
                                  pattern_hash: str | None = None) -> list[dict]:
    """Read the immutable snapshot, creating it only while the match is upcoming."""
    async with get_session() as session:
        snapshot = await session.get(AnalysisSnapshot, (row.match_id, RULE_VERSION))
        if snapshot is not None:
            _snapshot_finalized_put(_snapshot_cache_key(row.match_id))
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
            return await _legacy_v4_picks(session, row.match_id)
        picks, _ = await capture_recommendations(
            session,
            match_id=row.match_id,
            analyzed_at=current.analyzed_at,
            captured_at=captured_at,
            kickoff_time=current.kickoff_time,
            league_name=current.league_name,
            league_code=current.league_code,
            patterns=patterns,
            pattern_hash=pattern_hash,
        )
        if picks is not None:
            _snapshot_finalized_put(_snapshot_cache_key(row.match_id))
            return picks
    return []


async def _refresh_cached_recommendations(response: AnalyzeResponse) -> AnalyzeResponse:
    """Keep the fast analysis cache while reading externally written snapshots fresh."""
    if not isinstance(response, AnalyzeResponse):
        return response
    if response.skipped:
        return response
    match_id = response.match_id
    snapshot_key = _snapshot_cache_key(match_id)
    if snapshot_key in _snapshot_finalized or response.ft_recommendations:
        return response
    now = time.monotonic()
    if now - _snapshot_checked_at.get(snapshot_key, 0.0) < SNAPSHOT_POLL_TTL:
        return response
    _snapshot_checked_at[snapshot_key] = now
    try:
        async with get_session() as session:
            snapshot = await session.get(
                AnalysisSnapshot, (match_id, RULE_VERSION),
            )
    except Exception as exc:
        log.warning("Snapshot cache yenilemesi başarısız [%s]: %s", response.match_id, exc)
        return response
    if snapshot is not None:
        _snapshot_finalized_put(snapshot_key)
    picks = snapshot.picks if snapshot and isinstance(snapshot.picks, list) else []
    # İki taraf da aynı şemadan geçirilir: eski sürüm seçimlerinde olmayan yeni alanlar fark sayılmaz.
    normalized = [RecommendationOut.model_validate(pick).model_dump() for pick in picks]
    if [item.model_dump() for item in response.ft_recommendations] == normalized:
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

    patterns: dict[str, dict | None] = {
        key: getattr(row, key)
        for family in FAMILIES for key in pattern_keys(family)
    }
    # Hiç hesaplanmamış maç her zaman hesaplanır; ayarı eskimiş aileler sadece
    # maç başlamadan yenilenir (bitmiş maçın tahmin anındaki sonucu sabit kalır).
    stale = stale_families(row)
    upcoming = row.kickoff_time is not None and row.kickoff_time > datetime.now(timezone.utc)
    to_compute = stale if (row.pattern_computed_at is None or upcoming) else []
    if to_compute:
        log.info("Pattern hesaplanıyor %s: %s", to_compute, mid)
        as_of = pattern_as_of(row.analyzed_at, row.kickoff_time)
        fresh = await compute_all_patterns(
            match_id=mid,
            ht_scores=(ht_s1, ht_sx, ht_s2),
            h2_scores=(h2_s1, h2_sx, h2_s2),
            ft_scores=(ft_s1, ft_sx, ft_s2),
            ft_ratios=ft_ratios,
            as_of=as_of,
            league_name=row.league_name,
            families=to_compute,
        )
        patterns.update(fresh)
        try:
            await update_match_patterns(mid, fresh, expected_analyzed_at=row.analyzed_at,
                                        computed_as_of=as_of)
        except StalePatternWrite:
            raise HTTPException(409, "Analiz bu sırada güncellendi. Lütfen yeniden deneyin.")
        except Exception:
            log.warning("Pattern kaydedilemedi [%s]; hesaplanan yanıt kullanılacak", mid, exc_info=True)

    ht_b, ht_c, ht_d = (_pat(patterns[f"pattern_ht_{f}"]) for f in FAMILIES)
    h2_b, h2_c, h2_d = (_pat(patterns[f"pattern_h2_{f}"]) for f in FAMILIES)
    ft_b, ft_c, ft_d = (_pat(patterns[f"pattern_ft_{f}"]) for f in FAMILIES)

    current = pattern_hashes()
    shown_hash = hash_string({
        f: current[f] if f in to_compute else getattr(row, f"pattern_{f}_hash") for f in FAMILIES
    })
    try:
        recommendations = await _frozen_recommendations(row, patterns, shown_hash)
    except Exception:
        # Tahmin dondurma hatası analiz sayfasını düşürmemeli; bir sonraki ziyarette yeniden denenir.
        log.error("Maç öncesi seçim dondurulamadı [%s]", mid, exc_info=True)
        recommendations = []
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
        ht_d=ht_d, h2_d=h2_d, ft_d=ft_d,
        trends=_trends_parse(row.trends),
        recommendation_rule_version=RULE_VERSION,
        ft_recommendations=recommendations,
        pattern_hash=shown_hash,
        recommendation_pattern_hash=_recommendation_hash(recommendations),
    )


def _recommendation_hash(picks: list[dict]) -> str | None:
    return next((p.get("pattern_hash") for p in picks if isinstance(p, dict) and p.get("pattern_hash")), None)


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


def _skipped_response(
    match_id: str, home_team: str, away_team: str,
    league_code: str, reason: str | None = None,
) -> AnalyzeResponse:
    return AnalyzeResponse(
        match_id=match_id, home_team=home_team, away_team=away_team,
        league_code=league_code, season="",
        ht=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
        half2=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
        ft=PeriodOut(scores_1=[], scores_x=[], scores_2=[]),
        skipped=True, skip_reason=reason,
    )


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
            response = _skipped_response(
                match_id,
                fixture.get("home_team") or (db_row.home_team if db_row else ""),
                fixture.get("away_team") or (db_row.away_team if db_row else ""),
                fixture.get("league_code") or "",
                "not_league_match",
            )
            cache_put(match_id, response)
            return response

        if db_row is not None:
            if not is_supported_league(db_row.league_name, db_row.league_code):
                response = _skipped_response(
                    match_id, db_row.home_team, db_row.away_team,
                    db_row.league_code or "", "not_league_match",
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
            response = _skipped_response(
                skipped.match_id, skipped.home_team, skipped.away_team,
                skipped.league_code, skipped.reason,
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
        return _skipped_response(
            match_id, raw.home_team, raw.away_team,
            raw.league_code or "",
            check.reason.value if check.reason else None,
        )

    result = analyze_match(raw)
    patterns = await compute_all_patterns(
        match_id=match_id,
        ht_scores=(result.ht.scores_1, result.ht.scores_x, result.ht.scores_2),
        h2_scores=(result.half2.scores_1, result.half2.scores_x, result.half2.scores_2),
        ft_scores=(result.ft.scores_1, result.ft.scores_x, result.ft.scores_2),
        ft_ratios=result.ft.all_ratios,
        as_of=pattern_as_of(result.analyzed_at, raw.kickoff_time),
        league_name=match_league_name(raw.league_code, raw.league_name),
        teams=(raw.home_team, raw.away_team), kickoff=raw.kickoff_time,
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
        ht_d=_pat(patterns.get("pattern_ht_d")), h2_d=_pat(patterns.get("pattern_h2_d")),
        ft_d=_pat(patterns.get("pattern_ft_d")),
        trends=trends_data,
        recommendation_rule_version=RULE_VERSION,
        ft_recommendations=frozen_recommendations,
        pattern_hash=hash_string(pattern_hashes()),
        recommendation_pattern_hash=_recommendation_hash(frozen_recommendations),
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
    if len(_bg_queued) >= _BG_QUEUED_MAX:
        log.info("Arka plan kuyruğu dolu (%d), yeni ekleme atlanıyor", len(_bg_queued))
        return
    for m in matches:
        if cache_get(m.match_id) is None and m.match_id not in _bg_queued:
            _bg_queued.add(m.match_id)
            bg_queue.put_nowait(m.match_id)
    log.info("Arka plan kuyruğu: %d bekleyen maç", bg_queue.qsize())
