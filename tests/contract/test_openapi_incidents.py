"""Contract tests for the generated OpenAPI document (FR-111, NFR-081)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from aegis.main import create_app


def test_openapi_documents_incident_routes() -> None:
    with TestClient(create_app()) as client:
        spec = client.get("/openapi.json").json()

    paths = spec["paths"]
    collection = paths["/api/v1/incidents"]
    item = paths["/api/v1/incidents/{id}"]
    state = paths["/api/v1/incidents/{id}/state"]

    assert "post" in collection
    assert "get" in collection
    assert "get" in item
    assert "patch" in state
    assert collection["post"]["responses"]["201"]
    assert item["get"]["responses"]["200"]
    assert state["patch"]["responses"]["200"]
    assert paths["/api/v1/auth/token"]["post"]["responses"]["200"]


def test_openapi_error_schema_matches_system_boundaries() -> None:
    with TestClient(create_app()) as client:
        spec = client.get("/openapi.json").json()

    schemas = spec["components"]["schemas"]
    detail = schemas["ErrorDetail"]["properties"]
    assert set(detail) >= {"code", "message", "request_id"}
    envelope = schemas["ErrorResponse"]["properties"]
    assert "error" in envelope


def test_docs_ui_is_available() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/docs")

    assert response.status_code == 200
