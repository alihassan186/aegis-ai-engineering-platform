"""Postgres is reachable through the async SQLAlchemy session (Step 1.4)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from aegis.config.settings import Settings
from aegis.infrastructure.database.session import create_db_engine, create_session_factory

_DEFAULT_URL = "postgresql+asyncpg://aegis:aegis@127.0.0.1:5434/aegis"


@pytest.fixture
def database_url() -> str:
    return os.getenv("AEGIS_DATABASE_URL", _DEFAULT_URL)


async def test_session_opens_and_runs_select_1(database_url: str) -> None:
    settings = Settings(environment="test", database_url=database_url)
    engine = create_db_engine(settings)
    factory = create_session_factory(engine)
    try:
        session = factory()
        try:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
        finally:
            await session.close()
    finally:
        await engine.dispose()
