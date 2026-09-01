"""Webhook HMAC is required even when Postgres is not configured (THR-002)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aegis.main import create_app
from tests.helpers.auth import api_test_settings
from tests.helpers.webhook import encode_signal, signal_payload, signed_webhook_headers


def test_unsigned_webhook_returns_401_before_database() -> None:
    application = create_app(api_test_settings())
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/webhooks/incidents",
            content=encode_signal(signal_payload()),
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_webhook_without_secret_returns_503() -> None:
    application = create_app(api_test_settings(webhook_secret=""))
    raw = encode_signal(signal_payload())
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/webhooks/incidents",
            content=raw,
            headers=signed_webhook_headers(raw),
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "WEBHOOK_NOT_CONFIGURED"


def test_signed_webhook_without_database_returns_503() -> None:
    application = create_app(api_test_settings())
    raw = encode_signal(signal_payload())
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/webhooks/incidents",
            content=raw,
            headers=signed_webhook_headers(raw),
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_NOT_CONFIGURED"
