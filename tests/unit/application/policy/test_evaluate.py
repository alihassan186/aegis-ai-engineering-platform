"""Policy evaluation: default deny, specificity, destructive hard-stop (FR-067)."""

from __future__ import annotations

import pytest

from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.application.policy.evaluate import evaluate_policy
from aegis.application.policy.seed import seed_read_rules
from aegis.domain.gateway.enums import ActionClass
from aegis.domain.gateway.request import ToolInvokeRequest
from aegis.domain.policy.entity import WILDCARD, PolicyRule
from aegis.shared.exceptions import ValidationError


def test_default_deny_when_no_rules() -> None:
    verdict = evaluate_policy(
        [],
        tool_name="retrieve_knowledge",
        action_class=ActionClass.READ,
        agent_id="knowledge",
    )
    assert verdict.allowed is False
    assert verdict.reason == "denied:default"
    assert verdict.rule_id is None


def test_seeded_retrieve_allow_for_knowledge_agent() -> None:
    verdict = evaluate_policy(
        seed_read_rules(),
        tool_name="retrieve_knowledge",
        action_class=ActionClass.READ,
        agent_id="knowledge",
        service="payments-api",
    )
    assert verdict.allowed is True
    assert verdict.rule_id is not None


def test_more_specific_deny_for_search_code_wins() -> None:
    deny = PolicyRule.create(
        tool_name="search_code",
        action_class=ActionClass.READ,
        scope="code",
        allowed=False,
        reason="denied:search_code",
        actor="admin",
    )
    verdict = evaluate_policy(
        [*seed_read_rules(), deny],
        tool_name="search_code",
        action_class=ActionClass.READ,
        agent_id="code",
    )
    assert verdict.allowed is False
    assert verdict.reason == "denied:search_code"
    assert verdict.rule_id == deny.id


def test_destructive_is_denied_even_with_an_allow_row() -> None:
    with pytest.raises(ValidationError, match="destructive"):
        PolicyRule.create(
            tool_name="drop_database",
            action_class=ActionClass.DESTRUCTIVE,
            scope=WILDCARD,
            allowed=True,
            actor="admin",
        )
    verdict = evaluate_policy(
        seed_read_rules(),
        tool_name="drop_database",
        action_class=ActionClass.DESTRUCTIVE,
        agent_id="commander",
    )
    assert verdict.allowed is False
    assert verdict.reason == "denied:destructive"


def test_unknown_tool_is_denied() -> None:
    verdict = evaluate_policy(
        seed_read_rules(),
        tool_name="mystery",
        action_class=None,
        agent_id="knowledge",
    )
    assert verdict.allowed is False
    assert verdict.reason == "denied:unknown_tool"


def test_empty_policy_rules_deny_read_on_the_gateway() -> None:
    gateway = InvokeTool(
        tools={"retrieve_knowledge": lambda _p: "should-not-run"},
        policy_rules=(),
    )
    decision = gateway.invoke(
        ToolInvokeRequest(
            agent_id="knowledge",
            tool_name="retrieve_knowledge",
            parameters={"query": "latency"},
            incident_id="11111111-1111-1111-1111-111111111111",
        )
    )
    assert decision.allowed is False
    assert decision.reason == "denied:default"
    assert decision.result is None
