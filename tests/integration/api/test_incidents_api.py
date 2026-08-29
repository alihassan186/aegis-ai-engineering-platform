"""Incident REST API against Docker Postgres."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.api.dependencies import get_db
from aegis.config.settings import Settings
from aegis.main import create_app


@pytest.fixture
async def api_client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    application = create_app(Settings(environment="test", database_url=""))

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _create_payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "title": "Checkout latency",
        "affected_service": "payments-api",
        "severity": "high",
        "description": "p99 above SLO",
    }
    body.update(overrides)
    return body


async def test_create_incident_returns_201(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/api/v1/incidents", json=_create_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "open"
    assert body["title"] == "Checkout latency"
    assert body["request_id"]
    assert response.headers["x-request-id"] == body["request_id"]
    assert f"/api/v1/incidents/{body['id']}" in response.headers["location"]


async def test_get_incident_round_trip(api_client: httpx.AsyncClient) -> None:
    created = (await api_client.post("/api/v1/incidents", json=_create_payload())).json()

    response = await api_client.get(f"/api/v1/incidents/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["state"] == "open"


async def test_list_incidents_filters_by_service(api_client: httpx.AsyncClient) -> None:
    await api_client.post("/api/v1/incidents", json=_create_payload())
    await api_client.post(
        "/api/v1/incidents",
        json=_create_payload(title="Search", affected_service="search-api"),
    )

    response = await api_client.get(
        "/api/v1/incidents",
        params={"affected_service": "search-api"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"]
    assert [item["affected_service"] for item in body["items"]] == ["search-api"]


async def test_transition_state_returns_history(api_client: httpx.AsyncClient) -> None:
    created = (await api_client.post("/api/v1/incidents", json=_create_payload())).json()

    response = await api_client.patch(
        f"/api/v1/incidents/{created['id']}/state",
        json={"state": "investigating"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "investigating"
    assert len(body["state_history"]) == 1
    assert body["state_history"][0]["from_state"] == "open"
    assert body["state_history"][0]["to_state"] == "investigating"


async def test_get_missing_incident_returns_404_error_envelope(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/api/v1/incidents/11111111-1111-1111-1111-111111111111")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["message"]
    assert error["request_id"]
    assert response.headers["x-request-id"] == error["request_id"]


async def test_invalid_transition_returns_409(api_client: httpx.AsyncClient) -> None:
    created = (await api_client.post("/api/v1/incidents", json=_create_payload())).json()

    response = await api_client.patch(
        f"/api/v1/incidents/{created['id']}/state",
        json={"state": "resolved"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_TRANSITION"


async def test_invalid_body_returns_422(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/api/v1/incidents", json={"title": "x"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_echoes_incoming_request_id(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/incidents",
        json=_create_payload(),
        headers={"X-Request-ID": "client-trace-1"},
    )

    assert response.headers["x-request-id"] == "client-trace-1"
    assert response.json()["request_id"] == "client-trace-1"
