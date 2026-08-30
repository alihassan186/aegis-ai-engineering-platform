"""Shared Postgres session factory for integration and security tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aegis.config.settings import Settings
from aegis.infrastructure.database.session import create_db_engine

_DEFAULT_URL = "postgresql+asyncpg://aegis:aegis@127.0.0.1:5434/aegis"


def postgres_url() -> str:
    return os.getenv("AEGIS_DATABASE_URL", _DEFAULT_URL)


async def postgres_session(database_url: str) -> AsyncIterator[AsyncSession]:
    settings = Settings(environment="test", database_url=database_url)
    engine = create_db_engine(settings)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        factory = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            class_=AsyncSession,
            join_transaction_mode="create_savepoint",
        )
        session = factory()
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()
