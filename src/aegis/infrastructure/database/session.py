"""Async engine, session factory, and FastAPI session dependency (ADR-002)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from aegis.config.settings import Settings

# Connection pool settings for SQLAlchemy "asyncpg" driver.
# POOL_SIZE controls the number of persistent connections kept open at all times.
# MAX_OVERFLOW allows this many extra temporary connections if all pool slots are busy.

POOL_SIZE = 2        # Default: 2 connections always kept alive (good for small/tiny deployments/tests).
MAX_OVERFLOW = 3     # Default: up to 5 additional "overflow" connections during spikes.

# If you set both POOL_SIZE = 1 and MAX_OVERFLOW = 1:
# - At most 2 concurrent DB connections can exist: 1 pooled + 1 transient.
# - Benefits:
#   - Lower resource usage: reduces load on Postgres, useful for memory-limited or dev environments.
#   - Useful in CI/test scenarios where concurrency isn't needed.
# - Downsides:
#   - Increased chance of pool exhaustion ("too many connections") under concurrent requests.
#   - App performance could suffer if DB queries accumulate: only 2 can run at a time.
# Use 1/1 only for dev/test or when strictly limiting DB impact; for production, higher values prevent stalls.


def create_db_engine(settings: Settings) -> AsyncEngine:
    """Build the async engine. Does not open a connection until first use."""
    if not settings.database_url:
        raise ValueError("AEGIS_DATABASE_URL is required to create a database engine.")

    return create_async_engine(
        settings.database_url,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_pre_ping=True,
        echo=settings.debug,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def start_database(
    settings: Settings,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create the pool for application lifespan."""
    engine = create_db_engine(settings)
    return engine, create_session_factory(engine)


async def stop_database(engine: AsyncEngine | None) -> None:
    if engine is not None:
        await engine.dispose()


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield one AsyncSession per request and always close it."""
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise RuntimeError("Database is not configured. Set AEGIS_DATABASE_URL.")

    session: AsyncSession = factory()
    try:
        yield session
    finally:
        await session.close()
