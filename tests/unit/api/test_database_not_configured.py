"""HTTP behaviour when Postgres is not configured."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aegis.main import create_app
from tests.helpers.auth import api_test_settings, authorization_header


def test_create_incident_without_token_returns_401_before_database() -> None:
    application = create_app(api_test_settings())
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/incidents",
            json={
                "title": "Checkout latency",
                "affected_service": "payments-api",
                "severity": "high",
            },
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_create_incident_without_database_returns_503() -> None:
    application = create_app(api_test_settings())
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/incidents",
            json={
                "title": "Checkout latency",
                "affected_service": "payments-api",
                "severity": "high",
            },
            headers=authorization_header(),
        )

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "DATABASE_NOT_CONFIGURED"
    assert "AEGIS_DATABASE_URL" in error["message"]
