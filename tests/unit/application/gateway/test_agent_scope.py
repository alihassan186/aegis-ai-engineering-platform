"""Agent least privilege: bound identity, not JWT roles, not tool params (FR-074)."""

from __future__ import annotations

import pytest

from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.domain.auth.agent_identity import (
    AGENT_TOOL_GRANTS,
    AgentIdentity,
    agent_may_invoke,
)
from aegis.domain.gateway.request import ToolInvokeRequest
from aegis.shared.exceptions import ValidationError

_INCIDENT = "11111111-1111-1111-1111-111111111111"


def _request(
    tool_name: str,
    *,
    agent_id: str = "knowledge",
    parameters: dict[str, object] | None = None,
) -> ToolInvokeRequest:
    return ToolInvokeRequest(
        agent_id=agent_id,
        tool_name=tool_name,
        parameters=parameters or {"query": "latency"},
        incident_id=_INCIDENT,
    )


def test_registry_is_least_privilege() -> None:
    assert AGENT_TOOL_GRANTS[AgentIdentity.KNOWLEDGE] == frozenset({"retrieve_knowledge"})
    assert AGENT_TOOL_GRANTS[AgentIdentity.OBSERVABILITY] == frozenset({"fetch_signals"})
    assert AGENT_TOOL_GRANTS[AgentIdentity.CODE] == frozenset({"search_code", "list_deploys"})
    assert AGENT_TOOL_GRANTS[AgentIdentity.COMMANDER] == frozenset()
    assert AGENT_TOOL_GRANTS[AgentIdentity.RCA] == frozenset()
    assert AGENT_TOOL_GRANTS[AgentIdentity.MCP_CLIENT] == frozenset({"retrieve_knowledge"})
    assert not agent_may_invoke("mcp_client", "fetch_signals")
    assert not agent_may_invoke("knowledge", "search_code")
    assert not agent_may_invoke("system", "retrieve_knowledge")
    assert agent_may_invoke("code", "list_deploys")


def test_knowledge_calling_search_code_is_denied() -> None:
    def _search(_params: dict[str, object]) -> str:
        raise AssertionError("cross-agent tool must not run")

    gateway = InvokeTool(tools={"search_code": _search})
    decision = gateway.invoke(_request("search_code"))

    assert decision.allowed is False
    assert decision.reason == "denied:agent_scope"
    assert decision.agent_id == AgentIdentity.KNOWLEDGE
    assert decision.result is None


def test_observability_cannot_retrieve_knowledge() -> None:
    gateway = InvokeTool(tools={"retrieve_knowledge": lambda _p: "secret"})
    decision = gateway.invoke(_request("retrieve_knowledge", agent_id="observability"))
    assert decision.allowed is False
    assert decision.reason == "denied:agent_scope"


def test_commander_and_rca_have_no_external_tools() -> None:
    gateway = InvokeTool(tools={"retrieve_knowledge": lambda _p: "nope"})
    commander = gateway.invoke(_request("retrieve_knowledge", agent_id="commander"))
    rca = gateway.invoke(_request("fetch_signals", agent_id="rca"))
    assert commander.reason == "denied:agent_scope"
    assert rca.reason == "denied:agent_scope"


def test_unknown_agent_id_is_denied() -> None:
    gateway = InvokeTool(tools={"retrieve_knowledge": lambda _p: "nope"})
    decision = gateway.invoke(_request("retrieve_knowledge", agent_id="system"))
    assert decision.allowed is False
    assert decision.reason == "denied:unknown_agent"


def test_parameters_cannot_override_bound_identity() -> None:
    seen: list[dict[str, object]] = []

    def _retrieve(params: dict[str, object]) -> str:
        seen.append(dict(params))
        return "ok"

    def _search(_params: dict[str, object]) -> str:
        raise AssertionError("forged code identity must not run search_code")

    gateway = InvokeTool(
        tools={"retrieve_knowledge": _retrieve, "search_code": _search},
        bound_agent_id=AgentIdentity.KNOWLEDGE,
    )
    forged = gateway.invoke(
        _request(
            "search_code",
            agent_id="code",
            parameters={"agent_id": "code", "query": "payments"},
        )
    )
    allowed = gateway.invoke(
        _request(
            "retrieve_knowledge",
            agent_id="code",
            parameters={"agent_id": "code", "query": "latency"},
        )
    )

    assert forged.allowed is False
    assert forged.reason == "denied:agent_scope"
    assert forged.agent_id == AgentIdentity.KNOWLEDGE
    assert allowed.allowed is True
    assert allowed.agent_id == AgentIdentity.KNOWLEDGE
    assert seen == [{"query": "latency"}]
    assert "agent_id" not in seen[0]


def test_unbound_request_identity_ignores_param_agent_id() -> None:
    def _search(_params: dict[str, object]) -> str:
        raise AssertionError("param agent_id must not grant code tools")

    gateway = InvokeTool(tools={"search_code": _search})
    decision = gateway.invoke(
        _request("search_code", parameters={"agent_id": "code", "query": "x"})
    )
    assert decision.allowed is False
    assert decision.reason == "denied:agent_scope"
    assert decision.agent_id == "knowledge"


def test_bind_rejects_unknown_agent() -> None:
    with pytest.raises(ValidationError, match="unknown agent_id"):
        InvokeTool().bind("system")


def test_node_bind_closes_over_identity() -> None:
    gateway = InvokeTool(tools={"retrieve_knowledge": lambda _p: "ok"}).bind(
        AgentIdentity.KNOWLEDGE
    )
    assert gateway.bound_agent_id == AgentIdentity.KNOWLEDGE
    decision = gateway.invoke(_request("retrieve_knowledge", agent_id="observability"))
    assert decision.allowed is True
    assert decision.agent_id == AgentIdentity.KNOWLEDGE
