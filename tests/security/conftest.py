"""HTTP + Postgres fixtures for RBAC tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.api import make_api_client
from tests.helpers.db import postgres_session, postgres_url


@pytest.fixture
def database_url() -> str:
    return postgres_url()


@pytest.fixture
async def db_session(database_url: str) -> AsyncIterator[AsyncSession]:
    async for session in postgres_session(database_url):
        yield session


@pytest.fixture
async def api_client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    async for client in make_api_client(db_session):
        yield client
