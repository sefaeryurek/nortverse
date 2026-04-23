"""Supabase PostgreSQL bağlantısı.

DATABASE_URL ortam değişkeninden okunur (.env dosyası).
Async engine (asyncpg) + sync engine (psycopg2, Alembic için).
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import create_engine

load_dotenv()

_async_url = os.environ["DATABASE_URL"]

# Alembic için sync URL — sadece migration sırasında gerekli, API'de kullanılmaz
_sync_url = os.environ.get("DATABASE_URL_SYNC")

engine = create_async_engine(_async_url, pool_pre_ping=True)
sync_engine = create_engine(_sync_url, pool_pre_ping=True) if _sync_url else None

_SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Async veritabanı oturumu context manager."""
    async with _SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
