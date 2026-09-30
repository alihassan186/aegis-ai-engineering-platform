"""Policy admin RBAC: viewer GET 403, engineer POST 403 (FR-066, FR-071)."""

from __future__ import annotations

from uuid import uuid4

import httpx

from aegis.domain.auth.enums import Role
from tests.helpers.auth import authorization_header

_DENY_SEARCH = {
    "tool_name": "search_code",
    "action_class": "read",
    "scope": "code",
    "allowed": False,
    "reason": "denied:search_code",
}


async def test_unauthenticated_list_returns_401(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/v1/policy/rules")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_viewer_get_returns_403(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/api/v1/policy/rules",
        headers=authorization_header(Role.VIEWER),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_engineer_post_rule_returns_403(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/policy/rules",
        json=_DENY_SEARCH,
        headers=authorization_header(Role.ENGINEER),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_admin_lists_seeded_retrieve_and_can_deny_search_code(
    api_client: httpx.AsyncClient,
) -> None:
    admin = authorization_header(Role.ADMIN)
    listed = await api_client.get("/api/v1/policy/rules", headers=admin)
    assert listed.status_code == 200
    names = {item["tool_name"] for item in listed.json()["items"]}
    assert "retrieve_knowledge" in names
    assert "search_code" in names

    created = await api_client.post("/api/v1/policy/rules", json=_DENY_SEARCH, headers=admin)
    assert created.status_code == 201
    body = created.json()
    assert body["tool_name"] == "search_code"
    assert body["scope"] == "code"
    assert body["allowed"] is False
    assert body["created_by"] == "test-user"


async def test_admin_cannot_allow_destructive(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/policy/rules",
        json={
            "tool_name": "drop_database",
            "action_class": "destructive",
            "scope": "*",
            "allowed": True,
        },
        headers=authorization_header(Role.ADMIN),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_admin_get_missing_rule_returns_404(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        f"/api/v1/policy/rules/{uuid4()}",
        headers=authorization_header(Role.ADMIN),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
