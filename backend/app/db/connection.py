"""PostgreSQL bağlantısı.

DATABASE_URL ortam değişkeninden okunur (.env dosyası).
Async engine (asyncpg) + sync engine (psycopg2, Alembic için).

Pool/cache parametreleri env-driven:
- Supabase PgBouncer (transaction mode): DB_POOL_SIZE=2, DB_MAX_OVERFLOW=0, DB_STATEMENT_CACHE_SIZE=0
- Oracle / direct PostgreSQL: DB_POOL_SIZE=5, DB_MAX_OVERFLOW=5, DB_STATEMENT_CACHE_SIZE=100 (defaultlar)
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

load_dotenv()

def normalize_async_url(value: str):
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://"):]
    return make_url(value).set(drivername="postgresql+asyncpg")


_async_url = os.environ.get("DATABASE_URL")

# Alembic için sync URL — sadece migration sırasında gerekli, API'de kullanılmaz
_sync_url = os.environ.get("DATABASE_URL_SYNC")

_pool_size = int(os.environ.get("DB_POOL_SIZE", "5"))
_max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "5"))
_statement_cache_size = int(os.environ.get("DB_STATEMENT_CACHE_SIZE", "100"))

engine = create_async_engine(
    normalize_async_url(_async_url),
    pool_pre_ping=True,
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    connect_args={"statement_cache_size": _statement_cache_size},
) if _async_url else None
sync_engine = create_engine(_sync_url, pool_pre_ping=True) if _sync_url else None

_SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Async veritabanı oturumu context manager."""
    if engine is None:
        raise RuntimeError("DATABASE_URL yapılandırılmamış")
    async with _SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
