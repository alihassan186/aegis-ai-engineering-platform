"""HTTP client fixture for /api/v1 tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers.api import make_api_client


@pytest.fixture
async def api_client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    async for client in make_api_client(db_session):
        yield client
