"""Incident RBAC (FR-071, FR-072, THR-011)."""

from __future__ import annotations

import httpx

from aegis.domain.auth.enums import Role
from tests.helpers.auth import authorization_header

_CREATE_BODY = {
    "title": "Checkout latency",
    "affected_service": "payments-api",
    "severity": "high",
}


async def test_unauthenticated_create_returns_401(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/api/v1/incidents", json=_CREATE_BODY)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_viewer_can_list_and_get(api_client: httpx.AsyncClient) -> None:
    created = (
        await api_client.post(
            "/api/v1/incidents",
            json=_CREATE_BODY,
            headers=authorization_header(Role.ENGINEER),
        )
    ).json()

    listed = await api_client.get("/api/v1/incidents", headers=authorization_header(Role.VIEWER))
    fetched = await api_client.get(
        f"/api/v1/incidents/{created['id']}",
        headers=authorization_header(Role.VIEWER),
    )

    assert listed.status_code == 200
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


async def test_viewer_cannot_create(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/incidents",
        json=_CREATE_BODY,
        headers=authorization_header(Role.VIEWER),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_viewer_cannot_transition(api_client: httpx.AsyncClient) -> None:
    created = (
        await api_client.post(
            "/api/v1/incidents",
            json=_CREATE_BODY,
            headers=authorization_header(Role.ENGINEER),
        )
    ).json()

    response = await api_client.patch(
        f"/api/v1/incidents/{created['id']}/state",
        json={"state": "investigating"},
        headers=authorization_header(Role.VIEWER),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_engineer_can_create_and_transition(api_client: httpx.AsyncClient) -> None:
    auth = authorization_header(Role.ENGINEER)
    created = await api_client.post("/api/v1/incidents", json=_CREATE_BODY, headers=auth)
    assert created.status_code == 201

    response = await api_client.patch(
        f"/api/v1/incidents/{created.json()['id']}/state",
        json={"state": "investigating"},
        headers=auth,
    )

    assert response.status_code == 200
    assert response.json()["state"] == "investigating"


async def test_approver_and_admin_can_create(api_client: httpx.AsyncClient) -> None:
    for role in (Role.APPROVER, Role.ADMIN):
        response = await api_client.post(
            "/api/v1/incidents",
            json={**_CREATE_BODY, "title": f"{role.value} incident"},
            headers=authorization_header(role),
        )
        assert response.status_code == 201
