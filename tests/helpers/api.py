"""HTTP test client with JWT settings and DB override."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.api.dependencies import get_db
from aegis.main import create_app
from tests.helpers.auth import api_test_settings


async def make_api_client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    application = create_app(api_test_settings())

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
