"""Nortverse FastAPI uygulaması.

Slim hub: app oluşturma, middleware, lifespan, router kayıtları.
İş mantığı services.py'de, endpoint'ler routes_*.py modüllerinde.
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

# Windows'ta Playwright subprocess için ProactorEventLoop gerekiyor
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analysis.persist import PatternComputationError
from app.api.live_snapshot import shutdown_live_snapshot
from app.api.routes_admin import router as admin_router
from app.api.routes_analysis import router as analysis_router
from app.api.routes_fixture import router as fixture_router
from app.api.routes_results import router as results_router
from app.api.services import bg_worker, init_bg_queue, shutdown_bg_queue


# ─── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_bg_queue()
    worker = asyncio.create_task(bg_worker())
    try:
        yield
    finally:
        await shutdown_live_snapshot()
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        shutdown_bg_queue()


# ─── FastAPI uygulaması ───────────────────────────────────────────────────────

app = FastAPI(
    title="Nortverse API",
    description="Futbol maçı istatistik ve analiz sistemi",
    version="0.2.0",
    lifespan=lifespan,
)


@app.exception_handler(PatternComputationError)
async def pattern_computation_error(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, headers={"Cache-Control": "no-store"}, content={
        "detail": "Analiz arşivi şu anda işlenemiyor. Lütfen tekrar deneyin.",
    })


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Cache-Control middleware ─────────────────────────────────────────────────

_CACHE_RULES: dict[str, str] = {
    "/api/fixture": "public, s-maxage=300, stale-while-revalidate=60",
    "/api/results": "public, s-maxage=120, stale-while-revalidate=60",
    "/api/matches": "public, s-maxage=300, stale-while-revalidate=60",
    "/api/health": "public, s-maxage=30",
    "/api/analysis-evidence": "public, s-maxage=300, stale-while-revalidate=60",
}
_RECENT_SCORE_CACHE = "public, s-maxage=15, stale-while-revalidate=15"


def _recent_score_date(raw_date: str | None) -> bool:
    today = datetime.now(timezone(timedelta(hours=3))).date()
    try:
        target = date.fromisoformat(raw_date) if raw_date else today
    except ValueError:
        return False
    return today - timedelta(days=1) <= target <= today


@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    if request.method in ("GET", "HEAD") and response.status_code == 200:
        for prefix, rule in _CACHE_RULES.items():
            if request.url.path == prefix:
                response.headers["Cache-Control"] = (
                    _RECENT_SCORE_CACHE
                    if prefix in ("/api/fixture", "/api/results")
                    and _recent_score_date(request.query_params.get("date")) else rule
                )
                break
    if response.status_code >= 400:
        response.headers["Cache-Control"] = "no-store"
    return response


# ─── Router kayıtları ────────────────────────────────────────────────────────

app.include_router(fixture_router)
app.include_router(analysis_router)
app.include_router(results_router)
app.include_router(admin_router)
