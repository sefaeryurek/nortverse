"""Nortverse FastAPI uygulaması."""

from __future__ import annotations

import asyncio
import logging
import sys
import time
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
from app.analysis.pattern_b import find_pattern_b_matches
from app.analysis.pattern_c import find_pattern_c_all_periods
from app.analysis.pattern_stats import PatternResult
from app.db.connection import get_session
from app.db.models import Match
from app.scraper import fetch_fixture, fetch_match_detail

log = logging.getLogger(__name__)

# ─── Cache & eşzamanlılık ────────────────────────────────────────────────────

# Analiz sonuçları: match_id → AnalyzeResponse
_analysis_cache: dict[str, "AnalyzeResponse"] = {}
# Aynı match için tek seferde scrape garantisi
_analysis_locks: dict[str, asyncio.Lock] = {}

# Fixture cache: "YYYY-MM-DD" → (fetch_timestamp, [FixtureMatchOut])
_fixture_cache: dict[str, tuple[float, list]] = {}
FIXTURE_CACHE_TTL = 300.0  # 5 dakika

# Arka plan analiz kuyruğu (lifespan ile başlatılır)
_bg_queue: asyncio.Queue[str] | None = None
_bg_queued: set[str] = set()  # kuyruğa girmiş ama henüz tamamlanmamış match_id'ler


# ─── DB-first yardımcıları ───────────────────────────────────────────────────

async def _build_from_db(row: Match) -> "AnalyzeResponse | None":
    """DB satırından AnalyzeResponse üret — Playwright açılmaz, sadece B/C sorgusu."""
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

    async def _b(period: str, s1: list, sx: list, s2: list) -> Optional[PatternResult]:
        try:
            return await find_pattern_b_matches(period, s1, sx, s2)
        except Exception as exc:
            log.warning("Katman B [%s] DB-hit sorgusu başarısız [%s]: %s", period, row.match_id, exc)
            return None

    async def _c_all(ratios: dict) -> tuple:
        try:
            return await find_pattern_c_all_periods(ratios)
        except Exception as exc:
            log.warning("Katman C DB-hit sorgusu başarısız [%s]: %s", row.match_id, exc)
            return None, None, None

    (ht_b, h2_b, ft_b), c_results = await asyncio.gather(
        asyncio.gather(
            _b("ht", ht_s1, ht_sx, ht_s2),
            _b("h2", h2_s1, h2_sx, h2_s2),
            _b("ft", ft_s1, ft_sx, ft_s2),
        ),
        _c_all(ft_ratios),
    )
    ht_c, h2_c, ft_c = c_results

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
    )


async def _analyze_and_cache(match_id: str) -> "AnalyzeResponse":
    """DB kontrol et → bulursa B/C hesapla (hızlı). Yoksa Playwright scrape (yavaş)."""
    if match_id in _analysis_cache:
        return _analysis_cache[match_id]
    if match_id not in _analysis_locks:
        _analysis_locks[match_id] = asyncio.Lock()
    async with _analysis_locks[match_id]:
        if match_id in _analysis_cache:
            return _analysis_cache[match_id]

        # 1. DB kontrolü — önce DB'den dene (Playwright YOK)
        async with get_session() as session:
            db_row = (
                await session.execute(select(Match).where(Match.match_id == match_id))
            ).scalar_one_or_none()

        if db_row is not None:
            response = await _build_from_db(db_row)
            if response is not None:
                log.info("DB hit — anlık: %s", match_id)
                _analysis_cache[match_id] = response
                return response

        # 2. DB miss — Playwright ile scrape (ilk kez veya arşivde yok)
        log.info("DB miss — Playwright scrape: %s", match_id)
        response = await _do_analyze(match_id)
        _analysis_cache[match_id] = response
        return response


# ─── Arka plan kuyruğu ───────────────────────────────────────────────────────

async def _bg_worker() -> None:
    """Fixture yüklendikten sonra tüm maçları sırayla arka planda analiz eder."""
    assert _bg_queue is not None
    while True:
        match_id = await _bg_queue.get()
        try:
            if match_id not in _analysis_cache:
                await _analyze_and_cache(match_id)
                log.info("Arka plan analizi tamamlandı: %s", match_id)
        except Exception as exc:
            log.warning("Arka plan analizi başarısız [%s]: %s", match_id, exc)
        finally:
            _bg_queued.discard(match_id)
            _bg_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bg_queue
    _bg_queue = asyncio.Queue()
    task = asyncio.create_task(_bg_worker())
    yield
    task.cancel()
    try:
        await task
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


# ─── Response şemaları ────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str = "0.2.0"


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
    actual_ft_home: int
    actual_ft_away: int
    actual_ht_home: Optional[int]
    actual_ht_away: Optional[int]
    result: str          # "1" / "X" / "2"
    kg_var: bool         # Her iki takım gol attı
    over_25: bool        # Toplam gol >= 3
    katman_a_covered: bool   # Gerçek sonuç tipi Katman A'da var mıydı?


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

    async def _b(period: str, s1: list, sx: list, s2: list) -> Optional[PatternResult]:
        try:
            return await find_pattern_b_matches(period, s1, sx, s2)
        except Exception as e:
            log.warning("Katman B [%s] sorgusu başarısız [%s]: %s", period, match_id, e)
            return None

    async def _c_all(ratios: dict) -> tuple:
        try:
            return await find_pattern_c_all_periods(ratios)
        except Exception as e:
            log.warning("Katman C sorgusu başarısız [%s]: %s", match_id, e)
            return None, None, None

    (ht_b, h2_b, ft_b), c_results = await asyncio.gather(
        asyncio.gather(
            _b("ht", result.ht.scores_1, result.ht.scores_x, result.ht.scores_2),
            _b("h2", result.half2.scores_1, result.half2.scores_x, result.half2.scores_2),
            _b("ft", result.ft.scores_1, result.ft.scores_x, result.ft.scores_2),
        ),
        _c_all(result.ft.all_ratios),
    )
    ht_c, h2_c, ft_c = c_results

    return AnalyzeResponse(
        match_id=result.match_id,
        home_team=result.home_team,
        away_team=result.away_team,
        league_code=result.league_code,
        season=result.season,
        ht=PeriodOut(scores_1=result.ht.scores_1, scores_x=result.ht.scores_x, scores_2=result.ht.scores_2),
        half2=PeriodOut(scores_1=result.half2.scores_1, scores_x=result.half2.scores_x, scores_2=result.half2.scores_2),
        ft=PeriodOut(scores_1=result.ft.scores_1, scores_x=result.ft.scores_x, scores_2=result.ft.scores_2),
        ht_b=ht_b, ht_c=ht_c,
        h2_b=h2_b, h2_c=h2_c,
        ft_b=ft_b, ft_c=ft_c,
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/fixture", response_model=list[FixtureMatchOut])
async def fixture(target_date: Optional[str] = Query(None, alias="date")) -> list[FixtureMatchOut]:
    """Günlük Hot maçları döndürür. 5 dakika cache'lenir, tüm maçlar arka planda analiz kuyruğuna alınır."""
    parsed_date: Optional[date] = None
    if target_date:
        try:
            parsed_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. Kullanım: YYYY-MM-DD")

    cache_key = parsed_date.isoformat() if parsed_date else date.today().isoformat()

    # Fixture cache kontrolü
    if cache_key in _fixture_cache:
        ts, cached_result = _fixture_cache[cache_key]
        if time.time() - ts < FIXTURE_CACHE_TTL:
            log.info("Fixture cache hit: %s", cache_key)
            return cached_result

    matches = await fetch_fixture(target_date=parsed_date, only_hot=True)
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
    _fixture_cache[cache_key] = (time.time(), result)

    # Arka planda tüm maçları analiz kuyruğuna ekle
    if _bg_queue is not None:
        for m in matches:
            if m.match_id not in _analysis_cache and m.match_id not in _bg_queued:
                _bg_queued.add(m.match_id)
                await _bg_queue.put(m.match_id)
        log.info("Arka plan kuyruğu: %d maç eklendi (%s)", _bg_queue.qsize(), cache_key)

    return result


@app.get("/api/analyze/{match_id}", response_model=AnalyzeResponse)
async def get_analyze(match_id: str) -> AnalyzeResponse:
    """Maçı analiz eder. Cache'te varsa anında döner, yoksa scrape eder."""
    return await _analyze_and_cache(match_id)


@app.post("/api/analyze/{match_id}", response_model=AnalyzeResponse)
async def post_analyze(match_id: str) -> AnalyzeResponse:
    """Maçı her zaman scrape eder ve cache'i günceller."""
    response = await _do_analyze(match_id)
    _analysis_cache[match_id] = response
    return response


@app.get("/api/matches", response_model=list[MatchSummary])
async def list_matches(
    league: Optional[str] = Query(None, description="Lig kodu (örn: ENG PR)"),
    limit: int = Query(50, le=200),
) -> list[MatchSummary]:
    async with get_session() as session:
        stmt = select(Match).order_by(Match.analyzed_at.desc()).limit(limit)
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
    """Belirli bir tarihte biten maçları döndürür. Katman A tahmin kapsamı dahil."""
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
                .where(Match.actual_ft_home.isnot(None))
                .where(Match.kickoff_time >= day_start)
                .where(Match.kickoff_time <= day_end)
                .order_by(Match.kickoff_time)
            )
        ).scalars().all()

    out = []
    for row in rows:
        h = row.actual_ft_home
        a = row.actual_ft_away
        if h is None or a is None:
            continue

        result = "1" if h > a else ("2" if a > h else "X")
        kg_var = h > 0 and a > 0
        over_25 = (h + a) >= 3

        # Katman A: gerçek sonuç tipi için 3.5+ skor listesi doluysa kapsanmış
        if result == "1":
            covered_list = row.ft_scores_1 or []
        elif result == "2":
            covered_list = row.ft_scores_2 or []
        else:
            covered_list = row.ft_scores_x or []
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
            result=result,
            kg_var=kg_var,
            over_25=over_25,
            katman_a_covered=katman_a_covered,
        ))

    return out


@app.get("/api/match/{match_id}", response_model=MatchSummary)
async def get_match(match_id: str) -> MatchSummary:
    async with get_session() as session:
        row = (
            await session.execute(select(Match).where(Match.match_id == match_id))
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
