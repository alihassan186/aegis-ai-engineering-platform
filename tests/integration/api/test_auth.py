"""JWT login and token validation (FR-070, NFR-030)."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from aegis.domain.auth.enums import Role
from aegis.main import create_app
from tests.helpers.auth import api_test_settings, authorization_header


def test_dev_login_returns_bearer_token() -> None:
    application = create_app(api_test_settings(environment="development"))
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/auth/token",
            json={"username": "ali", "role": "engineer"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["role"] == "engineer"
    assert body["access_token"]
    assert body["request_id"]


def test_dev_login_rejects_unknown_role() -> None:
    application = create_app(api_test_settings(environment="development"))
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/auth/token",
            json={"username": "ali", "role": "superuser"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_production_does_not_expose_dev_login() -> None:
    application = create_app(
        api_test_settings(
            environment="production",
            database_url="postgresql+asyncpg://aegis:aegis@127.0.0.1:5434/aegis",
        )
    )
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/auth/token",
            json={"username": "ali", "role": "admin"},
        )

    assert response.status_code == 404


def test_login_without_jwt_secret_returns_503() -> None:
    application = create_app(api_test_settings(environment="development", jwt_secret=""))
    with TestClient(application) as client:
        response = client.post(
            "/api/v1/auth/token",
            json={"username": "ali", "role": "engineer"},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"


def test_incidents_without_token_return_401() -> None:
    application = create_app(api_test_settings())
    with TestClient(application) as client:
        response = client.get("/api/v1/incidents")

    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "UNAUTHENTICATED"
    assert error["request_id"]
    assert response.headers["www-authenticate"] == "Bearer"


def test_incidents_with_forged_token_return_401() -> None:
    application = create_app(api_test_settings())
    with TestClient(application) as client:
        response = client.get(
            "/api/v1/incidents",
            headers={"Authorization": "Bearer not-a-jwt"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_incidents_with_expired_token_return_401() -> None:
    application = create_app(api_test_settings())
    with TestClient(application) as client:
        response = client.get(
            "/api/v1/incidents",
            headers=authorization_header(expires_in=-1),
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_health_remains_unauthenticated() -> None:
    application = create_app(api_test_settings())
    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_dev_token_can_list_incidents(api_client: httpx.AsyncClient) -> None:
    login = await api_client.post(
        "/api/v1/auth/token",
        json={"username": "ali", "role": Role.ENGINEER.value},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = await api_client.get(
        "/api/v1/incidents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert "items" in response.json()
    assert response.json()["request_id"]
