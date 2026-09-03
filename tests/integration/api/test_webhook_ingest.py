"""Webhook ingest creates an open incident (FR-001, FR-113, THR-002)."""

from __future__ import annotations

import httpx

from tests.helpers.auth import authorization_header
from tests.helpers.webhook import encode_signal, isolated_signal_payload, signal_payload, signed_webhook_headers


async def test_valid_hmac_creates_open_incident(api_client: httpx.AsyncClient) -> None:
    payload = isolated_signal_payload()
    raw = encode_signal(payload)
    response = await api_client.post(
        "/api/v1/webhooks/incidents",
        content=raw,
        headers=signed_webhook_headers(raw),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "open"
    assert body["affected_service"] == payload["service"]
    assert body["title"] == payload["title"]
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


async def test_duplicate_webhooks_return_the_same_open_incident(
    api_client: httpx.AsyncClient,
) -> None:
    payload = isolated_signal_payload()
    raw = encode_signal(payload)
    headers = signed_webhook_headers(raw)
    first = await api_client.post("/api/v1/webhooks/incidents", content=raw, headers=headers)
    second = await api_client.post("/api/v1/webhooks/incidents", content=raw, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["state"] == "open"
    assert "duplicate signal at" in (second.json()["description"] or "")

    listed = await api_client.get(
        "/api/v1/incidents",
        params={"affected_service": payload["service"]},
        headers=authorization_header(),
    )
    created_ids = {first.json()["id"]}
    listed_ids = {item["id"] for item in listed.json()["items"]}
    assert created_ids <= listed_ids
    matching = [item for item in listed.json()["items"] if item["id"] == first.json()["id"]]
    assert len(matching) == 1


async def test_distinct_service_webhook_creates_another_incident(
    api_client: httpx.AsyncClient,
) -> None:
    payment_payload = isolated_signal_payload()
    order_payload = isolated_signal_payload(
        scenario="dependency_failure",
        title="Dependency failure on order",
    )
    payment_raw = encode_signal(payment_payload)
    order_raw = encode_signal(order_payload)
    payment = await api_client.post(
        "/api/v1/webhooks/incidents",
        content=payment_raw,
        headers=signed_webhook_headers(payment_raw),
    )
    order = await api_client.post(
        "/api/v1/webhooks/incidents",
        content=order_raw,
        headers=signed_webhook_headers(order_raw),
    )

    assert payment.status_code == 201
    assert order.status_code == 201
    assert payment.json()["id"] != order.json()["id"]
    assert payment.json()["affected_service"] == payment_payload["service"]
    assert order.json()["affected_service"] == order_payload["service"]


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
