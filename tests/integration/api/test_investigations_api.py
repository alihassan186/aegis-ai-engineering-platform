"""Investigation progress API against Docker Postgres (FR-022–024, FR-034, FR-035)."""

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


async def _investigating_incident(api_client: httpx.AsyncClient) -> str:
    auth = authorization_header(Role.ENGINEER)
    created = await api_client.post("/api/v1/incidents", json=_CREATE_BODY, headers=auth)
    assert created.status_code == 201
    incident_id = created.json()["id"]
    patched = await api_client.patch(
        f"/api/v1/incidents/{incident_id}/state",
        json={"state": "investigating"},
        headers=auth,
    )
    assert patched.status_code == 200
    return incident_id


async def test_unauthenticated_investigation_returns_401(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(f"/api/v1/incidents/{uuid4()}/investigation")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_unknown_incident_returns_404(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        f"/api/v1/incidents/{uuid4()}/investigation",
        headers=authorization_header(Role.ENGINEER),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["request_id"]


async def test_hmac_header_does_not_authenticate_investigation(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get(
        f"/api/v1/incidents/{uuid4()}/investigation",
        headers={"X-Aegis-Signature": "sha256=00"},
    )
    assert response.status_code == 401


async def test_engineer_get_sees_steps_after_fake_run(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    incident_id = await _investigating_incident(api_client)
    evidence_id, _version = await seed_fake_investigation(db_session, incident_id)

    response = await api_client.get(
        f"/api/v1/incidents/{incident_id}/investigation",
        headers=authorization_header(Role.ENGINEER),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"]
    assert body["incident_state"] == "investigating"
    assert body["hops"] == 2
    assert body["status"] == "pending_review"
    assert body["graph_resume_available"] is False
    assert "InMemorySaver" in body["resume_note"]
    assert "prompt" not in body
    assert [step["name"] for step in body["steps"]] == ["intake", "observability", "synthesize"]
    assert all(step["status"] in {"completed", "pending", "failed"} for step in body["steps"])
    assert str(evidence_id) in {str(item) for item in body["evidence_ids"]}
    assert body["rca"]["review_status"] == "pending_review"
    assert body["rca"]["summary"]


async def test_accept_identifies_incident_and_is_idempotent(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    auth = authorization_header(Role.ENGINEER)
    incident_id = await _investigating_incident(api_client)
    await seed_fake_investigation(db_session, incident_id)

    first = await api_client.post(
        f"/api/v1/incidents/{incident_id}/investigation/rca/accept",
        headers=auth,
    )
    second = await api_client.post(
        f"/api/v1/incidents/{incident_id}/investigation/rca/accept",
        headers=auth,
    )
    incident = await api_client.get(f"/api/v1/incidents/{incident_id}", headers=auth)

    assert first.status_code == 200
    assert first.json()["rca"]["review_status"] == "accepted"
    assert first.json()["incident_state"] == "identified"
    assert second.status_code == 200
    assert second.json()["rca"]["version"] == first.json()["rca"]["version"]
    assert incident.status_code == 200
    assert incident.json()["state"] == "identified"


async def test_reject_stays_investigating(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    auth = authorization_header(Role.ENGINEER)
    incident_id = await _investigating_incident(api_client)
    await seed_fake_investigation(db_session, incident_id)

    response = await api_client.post(
        f"/api/v1/incidents/{incident_id}/investigation/rca/reject",
        headers=auth,
    )
    incident = await api_client.get(f"/api/v1/incidents/{incident_id}", headers=auth)

    assert response.status_code == 200
    assert response.json()["rca"]["review_status"] == "rejected"
    assert response.json()["escalate_reason"] == "rca_rejected"
    assert incident.json()["state"] == "investigating"


async def test_amend_creates_version_two(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    auth = authorization_header(Role.ENGINEER)
    incident_id = await _investigating_incident(api_client)
    await seed_fake_investigation(db_session, incident_id)

    response = await api_client.post(
        f"/api/v1/incidents/{incident_id}/investigation/rca/amend",
        headers=auth,
        json={
            "summary": "Amended checkout latency",
            "root_cause": "Bad deploy plus saturated workers",
            "contributing_factors": ["deploy 2.8.1"],
            "confidence": 0.9,
            "status": "hypothesis",
            "recommended_actions": ["roll back payment"],
        },
    )

    assert response.status_code == 200
    versions = response.json()["rca_versions"]
    assert [item["version"] for item in versions] == [1, 2]
    assert versions[0]["version_kind"] == "original"
    assert versions[1]["version_kind"] == "amended"
    assert versions[1]["review_status"] == "pending_review"
    assert versions[1]["summary"] == "Amended checkout latency"


async def test_pause_and_resume_are_idempotent_flags(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    auth = authorization_header(Role.ENGINEER)
    incident_id = await _investigating_incident(api_client)
    await seed_fake_investigation(db_session, incident_id)

    paused = await api_client.post(
        f"/api/v1/incidents/{incident_id}/investigation/pause",
        headers=auth,
    )
    again = await api_client.post(
        f"/api/v1/incidents/{incident_id}/investigation/pause",
        headers=auth,
    )
    resumed = await api_client.post(
        f"/api/v1/incidents/{incident_id}/investigation/resume",
        headers=auth,
    )

    assert paused.status_code == 200
    assert paused.json()["paused"] is True
    assert paused.json()["graph_resume_available"] is False
    assert again.json()["paused"] is True
    assert resumed.status_code == 200
    assert resumed.json()["paused"] is False


async def test_manual_evidence_is_redacted(
    api_client: httpx.AsyncClient,
) -> None:
    auth = authorization_header(Role.ENGINEER)
    incident_id = await _investigating_incident(api_client)

    response = await api_client.post(
        f"/api/v1/incidents/{incident_id}/investigation/evidence",
        headers=auth,
        json={"summary": "checked logs key=AKIAIOSFODNN7EXAMPLE"},
    )

    assert response.status_code == 201
    assert "AKIAIOSFODNN7EXAMPLE" not in response.json()["summary"]
    assert response.json()["source"] == "manual"
    assert response.json()["kind"] == "note"
