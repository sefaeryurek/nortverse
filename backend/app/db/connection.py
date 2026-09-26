"""PostgreSQL bağlantısı.

DATABASE_URL ortam değişkeninden okunur (.env dosyası).
Async engine (asyncpg) + sync engine (psycopg2, Alembic için).

Pool/cache parametreleri env-driven:
- Neon pooler / Supabase PgBouncer: DB_POOL_SIZE=2, DB_MAX_OVERFLOW=0, DB_STATEMENT_CACHE_SIZE=0
- Direct PostgreSQL: DB_POOL_SIZE=5, DB_MAX_OVERFLOW=5, DB_STATEMENT_CACHE_SIZE=100 (defaultlar)
"""

import os
import ssl as _ssl
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

load_dotenv()

_ASYNCPG_STRIP_PARAMS = {"channel_binding", "sslmode"}

def normalize_async_url(value: str):
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://"):]
    url = make_url(value).set(drivername="postgresql+asyncpg")
    stripped = {k: v for k, v in url.query.items() if k not in _ASYNCPG_STRIP_PARAMS}
    if len(stripped) != len(url.query):
        url = url.set(query=stripped)
    return url


_async_url = os.environ.get("DATABASE_URL")

# Alembic için sync URL — sadece migration sırasında gerekli, API'de kullanılmaz
_sync_url = os.environ.get("DATABASE_URL_SYNC")

_pool_size = int(os.environ.get("DB_POOL_SIZE", "5"))
_max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "5"))
_statement_cache_size = int(os.environ.get("DB_STATEMENT_CACHE_SIZE", "100"))

_connect_args = {"statement_cache_size": _statement_cache_size}
if _async_url and "sslmode=" in _async_url and "sslmode=disable" not in _async_url:
    _connect_args["ssl"] = _ssl.create_default_context()

engine = create_async_engine(
    normalize_async_url(_async_url),
    pool_pre_ping=True,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    connect_args=_connect_args,
) if _async_url else None
sync_engine = create_engine(_sync_url, pool_pre_ping=True) if _sync_url else None

_SessionFactory = async_sessionmaker(engine, expire_on_commit=False) if engine else None


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Async veritabanı oturumu context manager."""
    if engine is None or _SessionFactory is None:
        raise RuntimeError("DATABASE_URL yapılandırılmamış")
    async with _SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
