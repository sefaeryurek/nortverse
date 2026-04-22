"""Nortverse FastAPI uygulaması.

Endpoints:
    GET  /api/health
    GET  /api/fixture?date=YYYY-MM-DD
    GET  /api/analyze/{match_id}   — DB cache, ilk seferde scrape
    POST /api/analyze/{match_id}   — Her zaman scrape (cache'i yeniler)
    GET  /api/matches?league=ENG PR&limit=50
    GET  /api/match/{match_id}
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select

from app.analysis import analyze_match, check_match_filters
from app.analysis.pattern_b import find_pattern_b_matches
from app.analysis.pattern_c import find_pattern_c_matches
from app.analysis.pattern_stats import PatternResult
from app.db.connection import get_session
from app.db.models import Match
from app.scraper import fetch_fixture, fetch_match_detail

log = logging.getLogger(__name__)

app = FastAPI(
    title="Nortverse API",
    description="Futbol maçı istatistik ve analiz sistemi",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache: match_id → AnalyzeResponse
_analysis_cache: dict[str, "AnalyzeResponse"] = {}
# Concurrency kontrolü: aynı match_id için tek seferde scrape
_analysis_locks: dict[str, asyncio.Lock] = {}


# --- Response şemaları ---

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
    # 6 pattern sonucu — periyot × arşiv
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


# --- Ortak analiz fonksiyonu ---

async def _do_analyze(match_id: str) -> AnalyzeResponse:
    """Maçı scrape et, 6 periyot × arşiv pattern hesapla."""
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

    # 6 pattern sorgusu (hata olursa None bırak)
    async def _b(period: str, s1: list, sx: list, s2: list) -> Optional[PatternResult]:
        try:
            return await find_pattern_b_matches(period, s1, sx, s2)
        except Exception as e:
            log.warning("Katman B [%s] sorgusu başarısız [%s]: %s", period, match_id, e)
            return None

    async def _c(period: str, ratios: dict) -> Optional[PatternResult]:
        try:
            return await find_pattern_c_matches(period, ratios)
        except Exception as e:
            log.warning("Katman C [%s] sorgusu başarısız [%s]: %s", period, match_id, e)
            return None

    ht_b, ht_c, h2_b, h2_c, ft_b, ft_c = await asyncio.gather(
        _b("ht", result.ht.scores_1, result.ht.scores_x, result.ht.scores_2),
        _c("ht", result.ht.all_ratios),
        _b("h2", result.half2.scores_1, result.half2.scores_x, result.half2.scores_2),
        _c("h2", result.half2.all_ratios),
        _b("ft", result.ft.scores_1, result.ft.scores_x, result.ft.scores_2),
        _c("ft", result.ft.all_ratios),
    )

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


# --- Endpoints ---

@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/fixture", response_model=list[FixtureMatchOut])
async def fixture(target_date: Optional[str] = Query(None, alias="date")) -> list[FixtureMatchOut]:
    """Günlük Hot maçları döndürür. date parametresi: YYYY-MM-DD. Boşsa bugün."""
    parsed_date: Optional[date] = None
    if target_date:
        try:
            parsed_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. Kullanım: YYYY-MM-DD")

    matches = await fetch_fixture(target_date=parsed_date, only_hot=True)
    return [
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


@app.get("/api/analyze/{match_id}", response_model=AnalyzeResponse)
async def get_analyze(match_id: str) -> AnalyzeResponse:
    """Maçı analiz eder. Cache'te varsa anında döner, yoksa scrape eder."""
    if match_id in _analysis_cache:
        log.info("Cache hit: %s", match_id)
        return _analysis_cache[match_id]

    # Aynı match_id için tek seferde scrape (concurrent request koruması)
    if match_id not in _analysis_locks:
        _analysis_locks[match_id] = asyncio.Lock()
    async with _analysis_locks[match_id]:
        # Lock alındıktan sonra tekrar kontrol
        if match_id in _analysis_cache:
            return _analysis_cache[match_id]
        response = await _do_analyze(match_id)
        _analysis_cache[match_id] = response
        return response


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
    """DB'deki analiz edilmiş maçları listeler."""
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


@app.get("/api/match/{match_id}", response_model=MatchSummary)
async def get_match(match_id: str) -> MatchSummary:
    """DB'den tek maç detayı döndürür."""
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
