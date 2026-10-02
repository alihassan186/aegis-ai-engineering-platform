"""MCP is a door, not a back door (Step 5.5 / FR-065)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aegis.application.gateway.registry import READ_TOOL_NAMES, WRITE_TOOL_NAMES
from aegis.application.investigation.collect import SpecialistPorts
from aegis.domain.auth.agent_identity import AgentIdentity
from aegis.domain.gateway.enums import ActionClass
from mcp.server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    McpSettings,
    build_mcp_server,
    create_app,
    validate_bind,
)


def _server():
    return build_mcp_server(ports=SpecialistPorts.memory(), token="mcp-test-token")


def test_list_tools_matches_registry() -> None:
    names = {item["name"] for item in _server().list_tools()}
    assert names == set(READ_TOOL_NAMES)
    assert WRITE_TOOL_NAMES == frozenset()
    assert "delete_rds" not in names
    assert "gh_pr_create" not in names


def test_retrieve_through_mcp_with_fake_store() -> None:
    decision = _server().call_tool(
        "retrieve_knowledge",
        {
            "query": "latency",
            "service": "payment",
            "scenario": "latency_spike",
            "agent_id": "knowledge",
            "action_class": "destructive",
        },
    )
    assert decision.allowed is True
    assert decision.reason == "allowed:read"
    assert decision.agent_id == AgentIdentity.MCP_CLIENT
    assert isinstance(decision.result, list)
    assert decision.result
    assert "latency" in str(decision.result[0]["text"]).lower()
    assert decision.result[0]["citation"]["document"].startswith("docs/knowledge/")


def test_invented_delete_rds_is_denied() -> None:
    decision = _server().call_tool(
        "delete_rds",
        {"please": "yes", "action_class": "read"},
    )
    assert decision.allowed is False
    assert decision.reason == "denied:destructive"
    assert decision.action_class is ActionClass.DESTRUCTIVE
    assert decision.result is None


def test_listed_but_ungranted_fetch_signals_is_denied() -> None:
    decision = _server().call_tool(
        "fetch_signals",
        {"service": "payment", "scenario": "latency_spike"},
    )
    assert decision.allowed is False
    assert decision.reason == "denied:agent_scope"
    assert decision.agent_id == AgentIdentity.MCP_CLIENT


def test_http_list_and_retrieve_require_token() -> None:
    server = _server()
    client = TestClient(create_app(server))
    denied = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert denied.status_code == 401

    listed = client.post(
        "/mcp",
        headers={"Authorization": "Bearer mcp-test-token"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert listed.status_code == 200
    tools = listed.json()["result"]["tools"]
    assert {item["name"] for item in tools} == set(READ_TOOL_NAMES)

    called = client.post(
        "/mcp",
        headers={"Authorization": "Bearer mcp-test-token"},
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "retrieve_knowledge",
                "arguments": {
                    "query": "latency",
                    "service": "payment",
                    "scenario": "latency_spike",
                },
            },
        },
    )
    body = called.json()["result"]
    assert called.status_code == 200
    assert body["allowed"] is True
    assert body["agent_id"] == "mcp_client"
    assert body["isError"] is False


def test_lan_bind_without_token_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-loopback"):
        validate_bind(McpSettings(host="0.0.0.0", token="", environment="development"))


def test_production_requires_loopback_and_token() -> None:
    with pytest.raises(ValueError, match="AEGIS_MCP_TOKEN"):
        validate_bind(McpSettings(host=DEFAULT_HOST, token="", environment="production"))
    with pytest.raises(ValueError, match="127.0.0.1"):
        validate_bind(McpSettings(host="0.0.0.0", token="secret", environment="production"))
    validate_bind(
        McpSettings(host=DEFAULT_HOST, port=DEFAULT_PORT, token="secret", environment="production")
    )
