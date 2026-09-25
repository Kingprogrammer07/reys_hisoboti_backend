"""Async database engine and session management for Neon PostgreSQL / SQLite.

Supports:
- Neon PostgreSQL with asyncpg driver (connection pooling, SSL, scale-to-zero)
- SQLite with aiosqlite driver (local dev / offline fallback)
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from . import config

log = logging.getLogger("reys.database")


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.x models."""
    pass


def get_async_database_url() -> str:
    """Normalize DATABASE_URL for asyncpg or fallback to aiosqlite."""
    raw_url = config.DATABASE_URL.strip()
    if not raw_url:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        sqlite_path = config.DATA_DIR / "reys.db"
        return f"sqlite+aiosqlite:///{sqlite_path.as_posix()}"

    parts = urlsplit(raw_url)
    scheme = parts.scheme
    netloc = parts.netloc
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
        netloc = netloc.replace("-pooler.", ".")
    elif scheme in ("sqlite", "sqlite3"):
        scheme = "sqlite+aiosqlite"

    # asyncpg expects 'ssl' parameter instead of 'sslmode' and does not accept channel_binding
    query_params = parse_qs(parts.query)
    query_params.pop("channel_binding", None)
    if "sslmode" in query_params:
        ssl_mode = query_params.pop("sslmode")[0]
        if ssl_mode in ("require", "verify-ca", "verify-full"):
            query_params["ssl"] = ["require"]

    new_query = urlencode(query_params, doseq=True)
    return urlunsplit((scheme, netloc, parts.path, new_query, parts.fragment))


ASYNC_DATABASE_URL = get_async_database_url()

_engine_kwargs: dict = {
    "echo": False,
    "pool_pre_ping": False,
}

if ASYNC_DATABASE_URL.startswith("postgresql+asyncpg"):
    _engine_kwargs.update({
        "pool_size": 15,
        "max_overflow": 25,
        "pool_recycle": 600,
        "connect_args": {"server_settings": {"application_name": "mandarin_reys_hisobot"}},
    })
elif ASYNC_DATABASE_URL.startswith("sqlite+aiosqlite"):
    _engine_kwargs.update({
        "connect_args": {"check_same_thread": False},
    })

engine: AsyncEngine = create_async_engine(ASYNC_DATABASE_URL, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async SQLAlchemy session with instant failover."""
    from .services import db_sync_worker

    status = db_sync_worker.get_database_status()
    if status.get("active_mode") == "sqlite" and config.DATABASE_BACKEND == "postgres":
        factory = db_sync_worker.get_sqlite_fallback_factory()
    else:
        factory = async_session_factory

    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all registered tables asynchronously."""
    # Ensure all models are imported before calling create_all
    from . import models  # noqa: F401

    log.info("initializing database tables with URL: %s", ASYNC_DATABASE_URL.split("@")[-1])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("database tables initialized successfully")


async def close_db() -> None:
    """Dispose database engine connection pool."""
    log.info("disposing database connection pool")
    await engine.dispose()
