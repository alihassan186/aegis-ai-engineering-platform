"""Tool abuse through the gateway: extra fields, traversal, huge payloads, wrong agent.

Every case must (1) be denied, (2) never reach the port behind the tool, and
(3) leave a deny row in the audit log (Step 5.8, FR-060 / FR-064 / FR-067).
"""

from __future__ import annotations

from typing import Any

import pytest

from aegis.application.audit.append_audit import AppendAudit
from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.application.gateway.limits import ToolLimits
from aegis.application.gateway.rate_limit import RateLimiter, ToolRateLimits
from aegis.application.gateway.registry import runners_for_ports
from aegis.core.protocols import CodeHit, ObservabilitySignal
from aegis.domain.gateway.enums import GatewayVerdict
from aegis.domain.gateway.request import ToolInvokeRequest
from tests.security.injection_harness import INCIDENT_ID, Spy


class _Ports:
    """One object standing in for all three ports. Counts every call."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_signals(self, **kwargs: Any) -> list[ObservabilitySignal]:
        self.calls.append("fetch_signals")
        return []

    def search(self, **kwargs: Any) -> list[CodeHit]:
        self.calls.append("search")
        return []

    def recent_deploys(self, **kwargs: Any) -> list[CodeHit]:
        self.calls.append("recent_deploys")
        return []

    def execute(self, query: str, **kwargs: Any):
        self.calls.append("execute")
        raise AssertionError("retrieve must not run")


class _Rig:
    def __init__(self) -> None:
        self.ports = _Ports()
        self.audit = AppendAudit()
        self.spy = Spy("drop_database")
        self.gateway = InvokeTool(
            tools={
                **runners_for_ports(
                    observability=self.ports,
                    code_search=self.ports,
                    retrieve=self.ports,
                    limits=ToolLimits(timeout_seconds=1.0),
                ),
                "drop_database": self.spy,
            },
            audit=self.audit,
            rate_limiter=RateLimiter(
                limits=ToolRateLimits(
                    window_seconds=60.0, per_tool_incident=1000, per_agent=1000, fail_closed=False
                )
            ),
        )

    def call(self, agent_id: str, tool_name: str, **parameters: Any):
        return self.gateway.invoke(
            ToolInvokeRequest(
                agent_id=agent_id,
                tool_name=tool_name,
                parameters=parameters,
                incident_id=INCIDENT_ID,
            )
        )

    def assert_denied(self, decision: Any, reason: str) -> None:
        assert decision.allowed is False
        assert decision.reason == reason
        assert self.ports.calls == []
        [entry] = self.audit.drain()
        assert entry.decision is GatewayVerdict.DENY
        assert entry.reason == reason
        assert str(entry.id) == decision.audit_id


@pytest.fixture
def rig() -> _Rig:
    return _Rig()


# ── extra fields ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("agent", "tool", "params"),
    [
        ("observability", "fetch_signals", {"service": "payment", "url": "http://evil/"}),
        ("code", "search_code", {"service": "payment", "path": "/etc/passwd"}),
        ("code", "list_deploys", {"service": "payment", "repo": "../../secrets"}),
        ("knowledge", "retrieve_knowledge", {"query": "x", "index": "audit_log"}),
        ("knowledge", "retrieve_knowledge", {"query": "x", "headers": {"Host": "evil"}}),
    ],
)
def test_extra_fields_are_rejected(rig: _Rig, agent: str, tool: str, params: dict) -> None:
    rig.assert_denied(rig.call(agent, tool, **params), "denied:invalid_params")


# ── path traversal ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "service",
    [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "payment/../../../root",
        "/etc/shadow",
        "payment\x00.py",
        "..",
    ],
)
def test_path_traversal_in_search_code_service_is_rejected(rig: _Rig, service: str) -> None:
    rig.assert_denied(
        rig.call("code", "search_code", service=service, scenario="latency_spike"),
        "denied:invalid_params",
    )


def test_path_traversal_in_scenario_is_rejected(rig: _Rig) -> None:
    rig.assert_denied(
        rig.call("code", "search_code", service="payment", scenario="../../app.py"),
        "denied:invalid_params",
    )


def test_nul_byte_payload_is_audited_without_the_nul(rig: _Rig) -> None:
    """Postgres JSONB cannot store NUL. A hostile value must not break the audit write."""
    rig.call("code", "search_code", service="payment\x00.py")

    [entry] = rig.audit.drain()
    assert "\x00" not in str(entry.input)
    assert "\\u0000" not in str(entry.input)


def test_traversal_is_rejected_for_every_read_tool_that_takes_a_service(rig: _Rig) -> None:
    for agent, tool in (
        ("observability", "fetch_signals"),
        ("code", "list_deploys"),
        ("knowledge", "retrieve_knowledge"),
    ):
        decision = rig.call(agent, tool, service="../../etc/passwd")
        assert decision.allowed is False
        assert decision.reason == "denied:invalid_params"
    assert rig.ports.calls == []
    assert len(rig.audit.drain()) == 3


# ── huge payload ─────────────────────────────────────────────────────────────


def test_huge_query_is_rejected_before_the_port_runs(rig: _Rig) -> None:
    decision = rig.call("knowledge", "retrieve_knowledge", query="A" * 5_000_000)

    rig.assert_denied(decision, "denied:payload_too_large")


def test_over_long_field_is_rejected(rig: _Rig) -> None:
    rig.assert_denied(
        rig.call("code", "search_code", service="payment", scenario="s" * 400),
        "denied:invalid_params",
    )


def test_limit_beyond_cap_is_clamped_not_amplified(rig: _Rig) -> None:
    decision = rig.call("observability", "fetch_signals", service="payment", limit=10**9)

    assert decision.allowed is True
    assert rig.ports.calls == ["fetch_signals"]


# ── wrong agent_id ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("agent", "tool"),
    [
        ("knowledge", "fetch_signals"),
        ("knowledge", "search_code"),
        ("observability", "retrieve_knowledge"),
        ("code", "retrieve_knowledge"),
        ("commander", "retrieve_knowledge"),
        ("rca", "fetch_signals"),
        ("mcp_client", "fetch_signals"),
        ("mcp_client", "search_code"),
    ],
)
def test_wrong_agent_for_a_tool_is_denied(rig: _Rig, agent: str, tool: str) -> None:
    rig.assert_denied(rig.call(agent, tool, service="payment"), "denied:agent_scope")


@pytest.mark.parametrize("agent", ["root", "admin", "system", "*", "knowledge-2"])
def test_invented_agent_id_is_denied(rig: _Rig, agent: str) -> None:
    decision = rig.call(agent, "retrieve_knowledge", query="x")

    assert decision.allowed is False
    assert rig.ports.calls == []
    [entry] = rig.audit.drain()
    assert entry.decision is GatewayVerdict.DENY


def test_forged_agent_id_parameter_cannot_change_the_caller(rig: _Rig) -> None:
    bound = rig.gateway.bind("knowledge")

    decision = bound.invoke(
        ToolInvokeRequest(
            agent_id="observability",
            tool_name="fetch_signals",
            parameters={"service": "payment", "agent_id": "observability"},
            incident_id=INCIDENT_ID,
        )
    )

    assert decision.allowed is False
    assert decision.reason == "denied:agent_scope"
    assert decision.agent_id == "knowledge"
    assert rig.ports.calls == []


# ── write tools that someone registered anyway ───────────────────────────────


@pytest.mark.parametrize("agent", ["knowledge", "observability", "code", "mcp_client"])
def test_a_registered_destructive_tool_still_never_runs(rig: _Rig, agent: str) -> None:
    decision = rig.call(agent, "drop_database", confirm=True)

    assert decision.allowed is False
    assert decision.reason == "denied:destructive"
    assert rig.spy.calls == []
    [entry] = rig.audit.drain()
    assert entry.action == "drop_database"
    assert entry.decision is GatewayVerdict.DENY


def test_unknown_tool_name_is_default_deny_with_audit(rig: _Rig) -> None:
    decision = rig.call("knowledge", "totally_new_tool", anything=1)

    assert decision.allowed is False
    assert decision.reason.startswith("denied:")
    assert rig.ports.calls == []
    [entry] = rig.audit.drain()
    assert entry.action == "totally_new_tool"
