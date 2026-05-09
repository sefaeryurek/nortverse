"""Nortverse FastAPI uygulaması."""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

# Windows'ta Playwright subprocess için ProactorEventLoop gerekiyor
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select

from app.analysis import analyze_match, check_match_filters
from app.analysis.league_filter import is_supported_league
from app.analysis.pattern_stats import PatternResult
from app.analysis.persist import compute_all_patterns, update_match_patterns
from app.analysis.trends import TrendsData, compute_trends
from app.db.connection import get_session
from app.db.models import FixtureCache, Match
from app.scraper import fetch_fixture, fetch_match_detail

log = logging.getLogger(__name__)

# ─── Cache & eşzamanlılık ────────────────────────────────────────────────────

# LRU bound — uzun süre çalışan container'da bellek koruması
_CACHE_MAX = 500

# Analiz sonuçları: match_id → AnalyzeResponse (LRU)
_analysis_cache: "OrderedDict[str, AnalyzeResponse]" = OrderedDict()
# Aynı match için tek seferde scrape garantisi (LRU)
_analysis_locks: "OrderedDict[str, asyncio.Lock]" = OrderedDict()


def _cache_put(match_id: str, value: "AnalyzeResponse") -> None:
    """LRU semantiği: ekle, en sona taşı, sınırı aşarsa en eskiyi at."""
    _analysis_cache[match_id] = value
    _analysis_cache.move_to_end(match_id)
    while len(_analysis_cache) > _CACHE_MAX:
        evicted, _ = _analysis_cache.popitem(last=False)
        _analysis_locks.pop(evicted, None)  # ilgili lock'u da temizle


def _cache_touch(match_id: str) -> None:
    """LRU sırasını güncellemek için: son erişimi en sona al."""
    if match_id in _analysis_cache:
        _analysis_cache.move_to_end(match_id)


def _get_or_make_lock(match_id: str) -> asyncio.Lock:
    """match_id için lock döndür; yeni oluşturulursa LRU'ya ekler."""
    lock = _analysis_locks.get(match_id)
    if lock is None:
        lock = asyncio.Lock()
        _analysis_locks[match_id] = lock
        while len(_analysis_locks) > _CACHE_MAX:
            _analysis_locks.popitem(last=False)
    else:
        _analysis_locks.move_to_end(match_id)
    return lock


# Fixture cache: "YYYY-MM-DD" → (fetch_timestamp, [FixtureMatchOut])
_fixture_cache: dict[str, tuple[float, list]] = {}
FIXTURE_CACHE_TTL = 600.0  # 10 dakika

# Arka plan analiz kuyruğu (lifespan ile başlatılır)
_bg_queue: asyncio.Queue[str] | None = None
_bg_queued: set[str] = set()  # kuyruğa girmiş ama henüz tamamlanmamış match_id'ler


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


def _trends(blob: dict | None) -> Optional[TrendsData]:
    """JSONB → TrendsData; None ise None döner."""
    if not blob:
        return None
    try:
        return TrendsData.model_validate(blob)
    except Exception as exc:
        log.warning("Saklı trends parse edilemedi: %s", exc)
        return None


async def _build_from_db(row: Match) -> "AnalyzeResponse | None":
    """DB satırından AnalyzeResponse üret.

    HIZLI YOL: 6 pattern kolonu da doluysa doğrudan deserialize → ~50ms.
    YAVAŞ YOL (lazy backfill): biri eksikse runtime hesabı yap + DB'ye geri yaz
    → bu maç için bir kerelik 1-3sn, sonraki tıklar hızlı.
    """
    if row.ft_scores_1 is None:
        return None  # Katman A verisi eksik, scrape gerekli

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

    # Hızlı yol: pattern kolonları doluysa direkt deserialize
    pattern_blobs = (
        row.pattern_ht_b, row.pattern_ht_c,
        row.pattern_h2_b, row.pattern_h2_c,
        row.pattern_ft_b, row.pattern_ft_c,
    )
    if all(p is not None for p in pattern_blobs):
        log.debug("Hızlı yol — saklı pattern'ler kullanıldı: %s", mid)
        ht_b, ht_c = _pat(row.pattern_ht_b), _pat(row.pattern_ht_c)
        h2_b, h2_c = _pat(row.pattern_h2_b), _pat(row.pattern_h2_c)
        ft_b, ft_c = _pat(row.pattern_ft_b), _pat(row.pattern_ft_c)
    else:
        # Yavaş yol: hesapla + DB'ye yaz (lazy backfill)
        log.info("Yavaş yol — pattern eksik, hesaplanıyor + DB'ye yazılıyor: %s", mid)
        patterns = await compute_all_patterns(
            match_id=mid,
            ht_scores=(ht_s1, ht_sx, ht_s2),
            h2_scores=(h2_s1, h2_sx, h2_s2),
            ft_scores=(ft_s1, ft_sx, ft_s2),
            ft_ratios=ft_ratios,
        )
        # Write-through: DB'ye sessiz yaz (hata olursa bile yanıt dönsün)
        await update_match_patterns(mid, patterns)

        ht_b, ht_c = _pat(patterns["pattern_ht_b"]), _pat(patterns["pattern_ht_c"])
        h2_b, h2_c = _pat(patterns["pattern_h2_b"]), _pat(patterns["pattern_h2_c"])
        ft_b, ft_c = _pat(patterns["pattern_ft_b"]), _pat(patterns["pattern_ft_c"])

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
        trends=_trends(row.trends),
    )


async def _analyze_db_only(match_id: str) -> bool:
    """Sadece DB hit denemesi — Playwright YOK.

    Arka plan worker'ı bunu kullanır. Container'ı Playwright fırtınasından korur.
    DB'de yoksa False döner; kullanıcı maça tıkladığında foreground tam analiz tetiklenir.
    """
    if match_id in _analysis_cache:
        _cache_touch(match_id)
        return True
    try:
        async with get_session() as session:
            row = (await session.execute(
                select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
            )).scalar_one_or_none()
        if row is None:
            return False
        response = await _build_from_db(row)
        if response is None:
            return False
        _cache_put(match_id, response)
        return True
    except Exception as exc:
        log.warning("DB-only analiz başarısız [%s]: %s", match_id, exc)
        return False


async def _analyze_and_cache(match_id: str) -> "AnalyzeResponse":
    """DB kontrol et → bulursa B/C hesapla (hızlı). Yoksa Playwright scrape (yavaş)."""
    if match_id in _analysis_cache:
        _cache_touch(match_id)
        return _analysis_cache[match_id]
    lock = _get_or_make_lock(match_id)
    async with lock:
        if match_id in _analysis_cache:
            _cache_touch(match_id)
            return _analysis_cache[match_id]

        # 1. DB kontrolü — önce DB'den dene (Playwright YOK)
        async with get_session() as session:
            db_row = (
                await session.execute(
                    select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
                )
            ).scalar_one_or_none()

        if db_row is not None:
            response = await _build_from_db(db_row)
            if response is not None:
                log.info("DB hit — anlık: %s", match_id)
                _cache_put(match_id, response)
                return response

        # 2. DB miss — Playwright ile scrape (ilk kez veya arşivde yok)
        log.info("DB miss — Playwright scrape: %s", match_id)
        response = await _do_analyze(match_id)
        _cache_put(match_id, response)
        return response


# ─── Arka plan kuyruğu ───────────────────────────────────────────────────────

async def _bg_worker() -> None:
    """Bülten yüklenince DB'de hazır olan maçların cache'ini ısıtır.

    KRİTİK: Sadece DB-hit dener; Playwright AÇMAZ. DB'de yoksa atlar.
    Aksi halde Cumartesi gibi pipeline'sız günlerde bütün container'ı boğar.
    """
    assert _bg_queue is not None
    while True:
        match_id = await _bg_queue.get()
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
            _bg_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bg_queue
    _bg_queue = asyncio.Queue()
    worker = asyncio.create_task(_bg_worker())
    yield
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass


# ─── FastAPI uygulaması ───────────────────────────────────────────────────────

app = FastAPI(
    title="Nortverse API",
    description="Futbol maçı istatistik ve analiz sistemi",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Sprint 8.10b — Cache-Control header'ları
# Cloudflare/Vercel edge cache için public cacheable endpoint'lere s-maxage uygula.
# Bu header CDN'e "edge'de N saniye sakla" der; origin (Railway → Supabase) çağrısı azalır.
# stale-while-revalidate: cache eski olsa bile döner, arka planda yenilenir.
_CACHE_RULES: dict[str, str] = {
    # Bülten: 5dk edge cache, 1dk stale-while-revalidate
    "/api/fixture": "public, s-maxage=300, stale-while-revalidate=60",
    # Sonuçlar: 2dk edge cache (saatlik update-scores ile uyumlu)
    "/api/results": "public, s-maxage=120, stale-while-revalidate=60",
    # Maç özeti: 5dk
    "/api/matches": "public, s-maxage=300, stale-while-revalidate=60",
    # Health: çok kısa, sadece HEAD ping mantıklı
    "/api/health": "public, s-maxage=30",
}


@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    # Sadece path eşleşen GET istekleri için cache header
    if request.method in ("GET", "HEAD"):
        for prefix, rule in _CACHE_RULES.items():
            if request.url.path.startswith(prefix):
                response.headers["Cache-Control"] = rule
                break
    return response


# ─── Response şemaları ────────────────────────────────────────────────────────

class DataQuality(BaseModel):
    """Sprint 8.9 — DB sağlığı/veri kalitesi göstergesi."""
    total_matches: int = 0
    active_matches: int = 0
    soft_deleted: int = 0
    non_league_active: int = 0  # 0 olmalı (yeni filtre sonrası)
    missing_pattern: int = 0
    missing_trends: int = 0
    missing_actual_score: int = 0
    quality_score: float = 100.0  # 0-100


class HealthResponse(BaseModel):
    """Hafif sağlık göstergesi — UptimeRobot her 5dk ping atıyor.

    Sprint 8.10: data_quality buradan KALDIRILDI (tüm matches taraması egress
    aşımına yol açıyordu). Detaylı kalite raporu için /api/admin/quality.
    """
    status: str
    version: str = "0.2.0"
    db_ok: bool
    last_pipeline_at: Optional[str] = None  # son maç analiz zamanı (ISO)
    last_fixture_cached_at: Optional[str] = None  # bugünün fixture cache zamanı (ISO)
    bg_queue_size: int = 0
    cached_analyses: int = 0


class FixtureMatchOut(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    league_code: str
    league_name: Optional[str]
    kickoff_time: Optional[str]


class PeriodOut(BaseModel):
    scores_1: list[str]
    scores_x: list[str]
    scores_2: list[str]


class AnalyzeResponse(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    league_code: str
    season: str
    ht: PeriodOut
    half2: PeriodOut
    ft: PeriodOut
    ht_b: Optional[PatternResult] = None
    ht_c: Optional[PatternResult] = None
    h2_b: Optional[PatternResult] = None
    h2_c: Optional[PatternResult] = None
    ft_b: Optional[PatternResult] = None
    ft_c: Optional[PatternResult] = None
    trends: Optional[TrendsData] = None  # form & H2H trendleri (FT periyodunda gösterilir)
    skipped: bool = False
    skip_reason: Optional[str] = None


class MatchSummary(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    league_code: Optional[str]
    season: Optional[str]
    actual_ft_home: Optional[int]
    actual_ft_away: Optional[int]
    actual_ht_home: Optional[int]
    actual_ht_away: Optional[int]
    ft_scores_1: Optional[list]
    ft_scores_x: Optional[list]
    ft_scores_2: Optional[list]


class ResultOut(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    league_code: Optional[str]
    league_name: Optional[str]
    kickoff_time: Optional[str]
    actual_ft_home: Optional[int] = None
    actual_ft_away: Optional[int] = None
    actual_ht_home: Optional[int] = None
    actual_ht_away: Optional[int] = None
    status: str          # "scheduled" / "live" / "finished"
    result: Optional[str] = None        # "1" / "X" / "2"  (sadece finished)
    kg_var: Optional[bool] = None       # sadece finished
    over_25: Optional[bool] = None      # sadece finished
    katman_a_covered: Optional[bool] = None  # sadece finished


# ─── Ortak analiz fonksiyonu ──────────────────────────────────────────────────

async def _do_analyze(match_id: str) -> AnalyzeResponse:
    raw = await fetch_match_detail(match_id)
    check = check_match_filters(raw)

    if not check.passed:
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
    )

    # Sonraki kullanıcılar hızlı görsün diye DB'ye tam upsert (analiz + pattern)
    try:
        from app.pipeline.runner import _upsert as _persist_full
        await _persist_full(result, raw, patterns)
    except Exception as exc:
        # ERROR seviyesi — DB yazısı başarısız olursa lazy-backfill yine tetiklenir
        # ama bu durum monitoring'de görünür olmalı (Railway logs)
        log.error(
            "Maç DB'ye kaydedilemedi (sonraki ziyarette tekrar Playwright açılacak) [%s]: %s",
            match_id, exc, exc_info=True,
        )

    # Form & H2H trendleri — runner.py _result_to_row üzerinden DB'ye yazıldı
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
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.api_route("/api/health", methods=["GET", "HEAD"], response_model=HealthResponse)
async def health() -> HealthResponse:
    """Sistem sağlık kontrolü — UptimeRobot/cron-job.org dış pinglerine uygun.

    HEAD ve GET'i de kabul eder (UptimeRobot free tier varsayılan HEAD gönderir).
    Container'ı uyandırır + DB durumu + son pipeline zamanı bilgisi döndürür.
    """
    from datetime import date as _date
    from sqlalchemy import func

    db_ok = False
    last_pipeline = None
    last_fixture_cached = None

    try:
        async with get_session() as session:
            # En son analiz edilen maç → pipeline canlı mı?
            row = await session.execute(
                select(func.max(Match.analyzed_at))
            )
            last_pipeline = row.scalar_one_or_none()

            # Bugünün fixture cache zamanı
            fc = await session.get(FixtureCache, _date.today().isoformat())
            if fc:
                last_fixture_cached = fc.cached_at

            db_ok = True
    except Exception as exc:
        log.warning("Health check DB sorgusu başarısız: %s", exc)

    # Sprint 8.10: data_quality KALDIRILDI — UptimeRobot 288 ping/gün × tüm matches
    # taraması egress aşımına yol açıyordu. Detaylı kalite için /api/admin/quality
    # veya `python -m app.cli.main audit-db` kullanın.
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        db_ok=db_ok,
        last_pipeline_at=last_pipeline.isoformat() if last_pipeline else None,
        last_fixture_cached_at=last_fixture_cached.isoformat() if last_fixture_cached else None,
        bg_queue_size=_bg_queue.qsize() if _bg_queue else 0,
        cached_analyses=len(_analysis_cache),
    )


@app.get("/api/admin/quality", response_model=DataQuality)
async def admin_quality() -> DataQuality:
    """Detaylı veri kalitesi raporu (Sprint 8.10).

    /api/health'tan ayrıldı — UptimeRobot otomatik çağırmaz.
    Manuel çağrı veya CLI `audit-db` ile aynı bilgiyi verir.
    """
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import or_

    async with get_session() as session:
        total = (await session.execute(select(func.count(Match.id)))).scalar() or 0
        active = (await session.execute(
            select(func.count(Match.id)).where(Match.deleted_at.is_(None))
        )).scalar() or 0
        soft_deleted = total - active

        # Aktif kupa maçları sayımı — sadece league_code/name çekilir, hafif
        active_rows = (await session.execute(
            select(Match.league_code, Match.league_name)
            .where(Match.deleted_at.is_(None))
        )).all()
        non_league = sum(
            1 for r in active_rows
            if not is_supported_league(r.league_name, r.league_code)
        )

        missing_pattern = (await session.execute(
            select(func.count(Match.id)).where(
                Match.deleted_at.is_(None),
                or_(Match.pattern_ft_b.is_(None), Match.pattern_ft_c.is_(None),
                    Match.pattern_ht_b.is_(None), Match.pattern_h2_b.is_(None)),
            )
        )).scalar() or 0
        missing_trends = (await session.execute(
            select(func.count(Match.id)).where(
                Match.deleted_at.is_(None), Match.trends.is_(None)
            )
        )).scalar() or 0
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=130)
        missing_actual = (await session.execute(
            select(func.count(Match.id)).where(
                Match.deleted_at.is_(None),
                Match.kickoff_time < cutoff,
                Match.actual_ft_home.is_(None),
            )
        )).scalar() or 0

    if total == 0:
        score = 0.0
    else:
        penalties = (
            (non_league / max(total, 1)) * 40
            + (missing_pattern / max(active, 1)) * 20
            + (missing_actual / max(active, 1)) * 30
            + (missing_trends / max(active, 1)) * 10
        )
        score = max(0.0, 100.0 - penalties)

    return DataQuality(
        total_matches=total,
        active_matches=active,
        soft_deleted=soft_deleted,
        non_league_active=non_league,
        missing_pattern=missing_pattern,
        missing_trends=missing_trends,
        missing_actual_score=missing_actual,
        quality_score=round(score, 1),
    )


@app.get("/api/fixture", response_model=list[FixtureMatchOut])
async def fixture(target_date: Optional[str] = Query(None, alias="date")) -> list[FixtureMatchOut]:
    """Günlük Hot maçları döndürür.

    3 katmanlı cache:
    1. Memory cache (5 dk TTL) — aynı istek tekrarı
    2. DB cache (kalıcı, geçmiş tarihler; bugün için 1 saat) — server restart'larına dayanıklı
    3. Playwright scrape — ilk kez veya cache süresi dolmuşsa
    """
    from datetime import datetime, timezone

    parsed_date: Optional[date] = None
    if target_date:
        try:
            parsed_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. Kullanım: YYYY-MM-DD")

    today = date.today()
    cache_key = parsed_date.isoformat() if parsed_date else today.isoformat()
    req_date = parsed_date or today

    # Tarih sınırı: 30 gün geçmiş, 14 gün gelecek dışına çıkılamaz
    # Sebep: yanlışlıkla uçuk tarih girilirse sürekli Playwright açılmasın
    from datetime import timedelta as _td
    max_past = today - _td(days=30)
    max_future = today + _td(days=14)
    if req_date < max_past or req_date > max_future:
        raise HTTPException(
            status_code=400,
            detail=f"Tarih sınırlar dışında. {max_past.isoformat()} ile {max_future.isoformat()} arası kabul edilir."
        )

    # 1. Memory cache
    if cache_key in _fixture_cache:
        ts, cached_result = _fixture_cache[cache_key]
        if time.time() - ts < FIXTURE_CACHE_TTL:
            log.info("Fixture memory cache hit: %s", cache_key)
            return cached_result

    # 2. DB cache — geçmiş tarihler kalıcı, bugün/gelecek 1 saat
    db_row = None
    try:
        async with get_session() as session:
            db_row = await session.get(FixtureCache, cache_key)
    except Exception as exc:
        log.warning("Fixture DB cache okunamadı (migration uygulanmamış olabilir): %s", exc)

    if db_row is not None:
        age = (datetime.now(timezone.utc) - db_row.cached_at).total_seconds()
        is_stale = req_date >= today and age >= 3600  # geçmiş tarih = kalıcı, diğerleri 1 saat
        if not is_stale:
            result = [FixtureMatchOut(**m) for m in db_row.matches_json]
            # Sprint 8.9: eski DB cache'lerde kupa olabilir — defansif filtre
            result = [m for m in result if is_supported_league(m.league_name, m.league_code)]
            _fixture_cache[cache_key] = (time.time(), result)
            log.info("Fixture DB cache hit: %s (%.0f sn önce, %d lig maçı)",
                     cache_key, age, len(result))
            _enqueue_bg_analysis(result)
            return result

    # 3. Playwright scrape — hard timeout ile sarmalı (Vercel SSR 25sn'de düşer)
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
    # Sprint 8.9: kupa/Avrupa/friendly maçlar bültene gelmesin
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

    _fixture_cache[cache_key] = (time.time(), result)
    _enqueue_bg_analysis(result)
    return result


def _enqueue_bg_analysis(matches: list[FixtureMatchOut]) -> None:
    """Arka plan analiz kuyruğuna maçları ekler."""
    if _bg_queue is None:
        return
    for m in matches:
        if m.match_id not in _analysis_cache and m.match_id not in _bg_queued:
            _bg_queued.add(m.match_id)
            _bg_queue.put_nowait(m.match_id)
    log.info("Arka plan kuyruğu: %d bekleyen maç", _bg_queue.qsize())


@app.get("/api/analyze/{match_id}", response_model=AnalyzeResponse)
async def get_analyze(match_id: str) -> AnalyzeResponse:
    """Maçı analiz eder. Cache'te varsa anında döner, yoksa scrape eder."""
    return await _analyze_and_cache(match_id)


@app.post("/api/analyze/{match_id}", response_model=AnalyzeResponse)
async def post_analyze(match_id: str) -> AnalyzeResponse:
    """Maçı her zaman scrape eder ve cache'i günceller."""
    response = await _do_analyze(match_id)
    _cache_put(match_id, response)
    return response


@app.get("/api/matches", response_model=list[MatchSummary])
async def list_matches(
    league: Optional[str] = Query(None, description="Lig kodu (örn: ENG PR)"),
    limit: int = Query(50, le=200),
) -> list[MatchSummary]:
    async with get_session() as session:
        stmt = (
            select(Match)
            .where(Match.deleted_at.is_(None))
            .order_by(Match.analyzed_at.desc())
            .limit(limit)
        )
        if league:
            stmt = stmt.where(Match.league_code == league)
        rows = (await session.execute(stmt)).scalars().all()

    return [
        MatchSummary(
            match_id=row.match_id,
            home_team=row.home_team,
            away_team=row.away_team,
            league_code=row.league_code,
            season=row.season,
            actual_ft_home=row.actual_ft_home,
            actual_ft_away=row.actual_ft_away,
            actual_ht_home=row.actual_ht_home,
            actual_ht_away=row.actual_ht_away,
            ft_scores_1=row.ft_scores_1,
            ft_scores_x=row.ft_scores_x,
            ft_scores_2=row.ft_scores_2,
        )
        for row in rows
    ]


@app.get("/api/results", response_model=list[ResultOut])
async def get_results(target_date: Optional[str] = Query(None, alias="date")) -> list[ResultOut]:
    """Belirli bir tarihte oynanan/oynanacak TÜM maçları döndürür.

    actual_ft_home filtresi YOK — canlı/başlamamış maçlar da listede yer alır.
    Frontend `status` alanına göre uygun gösterimi yapar:
      - "finished": skor + KG/2.5 istatistikleri
      - "live"    : Canlı rozet
      - "scheduled": Sadece saat
    """
    from datetime import datetime, timezone, timedelta

    if target_date:
        try:
            d = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. Kullanım: YYYY-MM-DD")
    else:
        d = date.today()

    # Günün başı ve sonu (UTC+3 Istanbul → UTC)
    day_start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone(timedelta(hours=3)))
    day_end = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone(timedelta(hours=3)))

    async with get_session() as session:
        rows = (
            await session.execute(
                select(Match)
                .where(Match.kickoff_time >= day_start)
                .where(Match.kickoff_time <= day_end)
                .where(Match.deleted_at.is_(None))  # Sprint 8.9
                .order_by(Match.kickoff_time)
            )
        ).scalars().all()

    now_utc = datetime.now(timezone.utc)
    out = []
    for row in rows:
        # Sprint 8.9: eski DB'de bulunan kupa maçları (Sprint 8.9 öncesi yazılmış)
        # /sonuclar'da görünmesin. Yeni filtre sayesinde yeni gelenler zaten yazılmıyor.
        if not is_supported_league(row.league_name, row.league_code):
            continue

        h = row.actual_ft_home
        a = row.actual_ft_away
        kickoff = row.kickoff_time

        # Status hesapla — sadece "finished" ve "live" maçlar gösterilir.
        # Henüz başlamamış (scheduled) ve skor güncellemesi bekleyen eski (stale)
        # maçlar /sonuclar'dan gizlenir; bültende veya update-scores cron'undan sonra görünür.
        if h is not None and a is not None:
            status = "finished"
        elif kickoff and now_utc >= kickoff and (now_utc - kickoff).total_seconds() < 130 * 60:
            # Kick-off geçmiş, son 130dk içinde, skor henüz yok → canlı
            status = "live"
        else:
            # scheduled (kickoff > now) veya stale (kickoff > 130dk önce, skor yok)
            continue

        result = None
        kg_var = None
        over_25 = None
        katman_a_covered = None
        if status == "finished" and h is not None and a is not None:
            result = "1" if h > a else ("2" if a > h else "X")
            kg_var = h > 0 and a > 0
            over_25 = (h + a) >= 3
            covered_list = (
                row.ft_scores_1 if result == "1"
                else row.ft_scores_2 if result == "2"
                else row.ft_scores_x
            ) or []
            katman_a_covered = len(covered_list) > 0

        out.append(ResultOut(
            match_id=row.match_id,
            home_team=row.home_team,
            away_team=row.away_team,
            league_code=row.league_code,
            league_name=row.league_name,
            kickoff_time=row.kickoff_time.isoformat() if row.kickoff_time else None,
            actual_ft_home=h,
            actual_ft_away=a,
            actual_ht_home=row.actual_ht_home,
            actual_ht_away=row.actual_ht_away,
            status=status,
            result=result,
            kg_var=kg_var,
            over_25=over_25,
            katman_a_covered=katman_a_covered,
        ))

    return out


@app.get("/api/match/{match_id}", response_model=MatchSummary)
async def get_match(match_id: str) -> MatchSummary:
    """Maçın özet bilgisi. DB'de yoksa Playwright ile çek + DB'ye kaydet, sonra dön.

    Hard timeout 25sn (Vercel SSR limiti dahilinde). Scrape de başarısız olursa 404.
    """
    async with get_session() as session:
        row = (
            await session.execute(
                select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
            )
        ).scalar_one_or_none()

    if not row:
        # Fallback: scrape + upsert + tekrar oku
        log.info("/api/match miss — Playwright fallback: %s", match_id)
        try:
            await asyncio.wait_for(_do_analyze(match_id), timeout=25.0)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail=f"Maç verisi çekilemedi (timeout): {match_id}")
        except Exception as exc:
            log.warning("Maç fallback scrape başarısız [%s]: %s", match_id, exc)
            raise HTTPException(status_code=404, detail=f"Maç bulunamadı: {match_id}")

        async with get_session() as session:
            row = (
                await session.execute(
                    select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail=f"Maç bulunamadı: {match_id}")

    return MatchSummary(
        match_id=row.match_id,
        home_team=row.home_team,
        away_team=row.away_team,
        league_code=row.league_code,
        season=row.season,
        actual_ft_home=row.actual_ft_home,
        actual_ft_away=row.actual_ft_away,
        actual_ht_home=row.actual_ht_home,
        actual_ht_away=row.actual_ht_away,
        ft_scores_1=row.ft_scores_1,
        ft_scores_x=row.ft_scores_x,
        ft_scores_2=row.ft_scores_2,
    )
