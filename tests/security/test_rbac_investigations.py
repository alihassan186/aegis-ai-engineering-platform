"""Investigation RBAC: viewer reads, engineer reviews (FR-071, FR-034)."""

from __future__ import annotations

from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.domain.auth.enums import Role
from tests.helpers.auth import authorization_header
from tests.helpers.investigation import seed_fake_investigation

_CREATE_BODY = {
    "title": "Checkout latency",
    "affected_service": "payments-api",
    "severity": "high",
}


async def _seeded_investigation(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> str:
    auth = authorization_header(Role.ENGINEER)
    created = await api_client.post("/api/v1/incidents", json=_CREATE_BODY, headers=auth)
    incident_id = created.json()["id"]
    await api_client.patch(
        f"/api/v1/incidents/{incident_id}/state",
        json={"state": "investigating"},
        headers=auth,
    )
    await seed_fake_investigation(db_session, incident_id)
    return incident_id


async def test_unauthenticated_accept_returns_401(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(f"/api/v1/incidents/{uuid4()}/investigation/rca/accept")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_viewer_can_get_but_cannot_accept(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    incident_id = await _seeded_investigation(api_client, db_session)
    viewer = authorization_header(Role.VIEWER)

    fetched = await api_client.get(
        f"/api/v1/incidents/{incident_id}/investigation",
        headers=viewer,
    )
    accepted = await api_client.post(
        f"/api/v1/incidents/{incident_id}/investigation/rca/accept",
        headers=viewer,
    )
    paused = await api_client.post(
        f"/api/v1/incidents/{incident_id}/investigation/pause",
        headers=viewer,
    )
    note = await api_client.post(
        f"/api/v1/incidents/{incident_id}/investigation/evidence",
        headers=viewer,
        json={"summary": "viewer note"},
    )

    assert fetched.status_code == 200
    assert accepted.status_code == 403
    assert accepted.json()["error"]["code"] == "FORBIDDEN"
    assert paused.status_code == 403
    assert note.status_code == 403


async def test_engineer_can_accept(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    incident_id = await _seeded_investigation(api_client, db_session)
    response = await api_client.post(
        f"/api/v1/incidents/{incident_id}/investigation/rca/accept",
        headers=authorization_header(Role.ENGINEER),
    )
    assert response.status_code == 200
    assert response.json()["incident_state"] == "identified"
