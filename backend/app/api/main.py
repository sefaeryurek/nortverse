"""Nortverse FastAPI uygulaması.

Slim hub: app oluşturma, middleware, lifespan, router kayıtları.
İş mantığı services.py'de, endpoint'ler routes_*.py modüllerinde.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

# Windows'ta Playwright subprocess için ProactorEventLoop gerekiyor
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def _configure_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    fmt = os.environ.get("LOG_FORMAT", "text")
    if fmt == "json":
        log_fmt = '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","msg":"%(message)s"}'
    else:
        log_fmt = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
    logging.basicConfig(level=level, format=log_fmt, force=True)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


_configure_logging()

# .env, app.config okunmadan yüklenmeli (aksi halde PATTERN_* ayarları API'de görünmez, CLI'da görünür).
from dotenv import load_dotenv

load_dotenv()

from app.config import ISTANBUL_TZ
from app.analysis.persist import PatternComputationError
from app.api.live_ledger import start_live_watcher, stop_live_watcher
from app.api.live_snapshot import shutdown_live_snapshot
from app.api.routes_admin import router as admin_router
from app.api.routes_analysis import router as analysis_router
from app.api.routes_evaluation import router as evaluation_router
from app.api.routes_fixture import router as fixture_router
from app.api.routes_ht import router as ht_router
from app.api.routes_live_ht import router as live_ht_router, start_ws_broadcaster, stop_ws_broadcaster
from app.api.routes_performance import router as performance_router
from app.api.routes_results import router as results_router
from app.api.services import bg_worker, init_bg_queue, shutdown_bg_queue


# ─── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_bg_queue()
    worker = asyncio.create_task(bg_worker())
    start_ws_broadcaster()
    start_live_watcher()
    try:
        yield
    finally:
        await stop_live_watcher()
        await stop_ws_broadcaster()
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
    version=__import__("app").__version__,
    lifespan=lifespan,
)


@app.exception_handler(PatternComputationError)
async def pattern_computation_error(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, headers={"Cache-Control": "no-store"}, content={
        "detail": "Analiz arşivi şu anda işlenemiyor. Lütfen tekrar deneyin.",
    })


_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:3000,https://nortverse.vercel.app",
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "HEAD", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization", "X-Admin-Key"],
)


# ─── Cache-Control middleware ─────────────────────────────────────────────────

_CACHE_RULES: dict[str, str] = {
    "/api/fixture": "public, s-maxage=300, stale-while-revalidate=60",
    "/api/results": "public, s-maxage=120, stale-while-revalidate=60",
    "/api/matches": "public, s-maxage=300, stale-while-revalidate=60",
    "/api/health": "public, s-maxage=30",
    "/api/evaluation": "public, s-maxage=300, stale-while-revalidate=60",
    "/api/performance/summary": "public, s-maxage=120, stale-while-revalidate=60",
    "/api/performance/predictions": "public, s-maxage=60, stale-while-revalidate=30",
    "/api/performance/backtest/runs": "public, s-maxage=300, stale-while-revalidate=60",
    "/api/performance/live-matches": "public, s-maxage=60, stale-while-revalidate=30",
}
_RECENT_SCORE_CACHE = "public, s-maxage=15, stale-while-revalidate=15"


def _recent_score_date(raw_date: str | None) -> bool:
    today = datetime.now(ISTANBUL_TZ).date()
    try:
        target = date.fromisoformat(raw_date) if raw_date else today
    except ValueError:
        return False
    return today - timedelta(days=1) <= target <= today


_req_log = logging.getLogger("nortverse.request")


@app.middleware("http")
async def add_cache_headers(request, call_next):
    import time as _time
    t0 = _time.monotonic()
    response = await call_next(request)
    elapsed_ms = round((_time.monotonic() - t0) * 1000)
    if request.url.path.startswith("/api/"):
        _req_log.info("%s %s → %d (%dms)", request.method, request.url.path, response.status_code, elapsed_ms)
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
app.include_router(evaluation_router)
app.include_router(live_ht_router)
app.include_router(ht_router)
app.include_router(performance_router)
app.include_router(admin_router)
