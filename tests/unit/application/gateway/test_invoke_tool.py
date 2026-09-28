"""Guardrail core: classify then allow/deny. Tool does not run on deny."""

from __future__ import annotations

import pytest

from aegis.application.gateway.classify import classify
from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.domain.gateway.enums import ActionClass
from aegis.domain.gateway.request import ToolInvokeRequest
from aegis.shared.exceptions import ValidationError


def _request(
    tool_name: str,
    *,
    action_class: str | None = None,
    parameters: dict[str, object] | None = None,
) -> ToolInvokeRequest:
    return ToolInvokeRequest(
        agent_id="knowledge",
        tool_name=tool_name,
        parameters=parameters or {"query": "latency"},
        incident_id="11111111-1111-1111-1111-111111111111",
        action_class=action_class,
    )


def test_classify_read_tools() -> None:
    assert classify("retrieve_knowledge") is ActionClass.READ
    assert classify("fetch_signals") is ActionClass.READ
    assert classify("search_code") is ActionClass.READ
    assert classify("drop_database") is ActionClass.DESTRUCTIVE
    assert classify("not_a_real_tool") is None


def test_read_tool_allow_returns_result() -> None:
    seen: list[dict[str, object]] = []

    def _retrieve(params: dict[str, object]) -> str:
        seen.append(dict(params))
        return "runbook excerpt"

    gateway = InvokeTool(tools={"retrieve_knowledge": _retrieve})
    decision = gateway.invoke(_request("retrieve_knowledge"))

    assert decision.allowed is True
    assert decision.reason == "allowed:read"
    assert decision.requires_approval is False
    assert decision.result == "runbook excerpt"
    assert decision.audit_id is None
    assert seen == [{"query": "latency"}]


def test_unknown_tool_deny_does_not_run_runner() -> None:
    def _boom(_params: dict[str, object]) -> str:
        raise AssertionError("unknown tool must not run")

    gateway = InvokeTool(tools={"mystery": _boom})
    decision = gateway.invoke(_request("mystery"))

    assert decision.allowed is False
    assert decision.reason == "denied:unknown_tool"
    assert decision.error == "denied:unknown_tool"
    assert decision.result is None


def test_drop_database_denied_even_if_registered_and_asks_nicely() -> None:
    def _drop(_params: dict[str, object]) -> str:
        raise AssertionError("destructive tool must not run")

    gateway = InvokeTool(tools={"drop_database": _drop})
    decision = gateway.invoke(
        _request(
            "drop_database",
            action_class="read",
            parameters={"please": "the test asks nicely"},
        )
    )

    assert decision.allowed is False
    assert decision.reason == "denied:destructive"
    assert decision.action_class is ActionClass.DESTRUCTIVE
    assert decision.requires_approval is False


def test_caller_action_class_is_ignored() -> None:
    gateway = InvokeTool(tools={"retrieve_knowledge": lambda _p: "ok"})
    claimed_read = _request("drop_database", action_class="read")
    assert claimed_read.claimed_action_class == "read"
    decision = gateway.invoke(claimed_read)
    assert decision.allowed is False
    assert decision.reason == "denied:destructive"


def test_high_risk_write_denied_with_requires_approval() -> None:
    def _pr(_params: dict[str, object]) -> str:
        raise AssertionError("high-risk write must not run")

    gateway = InvokeTool(tools={"gh_pr_create": _pr})
    decision = gateway.invoke(_request("gh_pr_create"))
    assert decision.allowed is False
    assert decision.requires_approval is True
    assert decision.reason == "denied:high_risk_write"


def test_output_is_redacted() -> None:
    gateway = InvokeTool(
        tools={"retrieve_knowledge": lambda _p: "token AKIAIOSFODNN7EXAMPLE in text"}
    )
    decision = gateway.invoke(_request("retrieve_knowledge"))
    assert decision.allowed is True
    assert "AKIAIOSFODNN7EXAMPLE" not in str(decision.result)
    assert "[REDACTED:aws_access_key]" in str(decision.result)


def test_not_registered_read_tool_is_denied() -> None:
    decision = InvokeTool().invoke(_request("retrieve_knowledge"))
    assert decision.allowed is False
    assert decision.reason == "denied:not_registered"


def test_empty_tool_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _request("   ")
