"""Alembic migration ortamı.

DATABASE_URL_SYNC önceliklidir (psycopg2 — sync bağlantı).
Yoksa DATABASE_URL'den otomatik üretilir (asyncpg → psycopg2 dönüşümü).
Bu sayede Docker entrypoint tek env var (DATABASE_URL) ile çalışır.
"""

import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

load_dotenv()


def _resolve_sync_url() -> str:
    sync_url = os.environ.get("DATABASE_URL_SYNC")
    if sync_url:
        return sync_url
    async_url = os.environ.get("DATABASE_URL")
    if not async_url:
        raise RuntimeError("DATABASE_URL_SYNC veya DATABASE_URL env var gerekli")
    # asyncpg → psycopg2 dönüşümü
    if async_url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg2://" + async_url[len("postgresql+asyncpg://"):]
    if async_url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + async_url[len("postgresql://"):]
    return async_url


config = context.config
config.set_main_option("sqlalchemy.url", _resolve_sync_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.db.models import Base  # noqa: E402
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
