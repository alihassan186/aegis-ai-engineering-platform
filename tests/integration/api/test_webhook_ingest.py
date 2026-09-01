"""Webhook ingest creates an open incident (FR-001, FR-113, THR-002)."""

from __future__ import annotations

import httpx

from tests.helpers.auth import authorization_header
from tests.helpers.webhook import encode_signal, signal_payload, signed_webhook_headers


async def test_valid_hmac_creates_open_incident(api_client: httpx.AsyncClient) -> None:
    raw = encode_signal(signal_payload())
    response = await api_client.post(
        "/api/v1/webhooks/incidents",
        content=raw,
        headers=signed_webhook_headers(raw),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "open"
    assert body["affected_service"] == "payment"
    assert body["title"] == "Latency spike on payment"
    assert body["severity"] == "high"
    assert "incident.signal.v1 source=simulator" in (body["description"] or "")
    assert f"/api/v1/incidents/{body['id']}" in response.headers["location"]

    fetched = await api_client.get(
        f"/api/v1/incidents/{body['id']}",
        headers=authorization_header(),
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]
    assert fetched.json()["state"] == "open"


async def test_bad_hmac_returns_401(api_client: httpx.AsyncClient) -> None:
    raw = encode_signal(signal_payload())
    headers = signed_webhook_headers(raw)
    headers["X-Aegis-Signature"] = "sha256=" + ("ab" * 32)
    response = await api_client.post(
        "/api/v1/webhooks/incidents",
        content=raw,
        headers=headers,
    )

    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "UNAUTHENTICATED"
    assert error["request_id"]
    assert "WWW-Authenticate" not in response.headers


async def test_missing_signature_returns_401(api_client: httpx.AsyncClient) -> None:
    raw = encode_signal(signal_payload())
    response = await api_client.post(
        "/api/v1/webhooks/incidents",
        content=raw,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_jwt_does_not_replace_hmac(api_client: httpx.AsyncClient) -> None:
    raw = encode_signal(signal_payload())
    response = await api_client.post(
        "/api/v1/webhooks/incidents",
        content=raw,
        headers={**authorization_header(), "Content-Type": "application/json"},
    )

    assert response.status_code == 401


async def test_duplicate_webhooks_create_two_incidents_until_dedup(
    api_client: httpx.AsyncClient,
) -> None:
    raw = encode_signal(signal_payload())
    headers = signed_webhook_headers(raw)
    first = await api_client.post("/api/v1/webhooks/incidents", content=raw, headers=headers)
    second = await api_client.post("/api/v1/webhooks/incidents", content=raw, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


async def test_manual_incidents_post_still_requires_jwt(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/incidents",
        json={
            "title": "Checkout latency",
            "affected_service": "payments-api",
            "severity": "high",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
