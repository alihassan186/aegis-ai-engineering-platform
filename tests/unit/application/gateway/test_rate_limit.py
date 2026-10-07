"""Per-agent / per-tool caps: Nth+1 deny + audit, not a 500 (FR-063)."""

from __future__ import annotations

from collections.abc import Sequence

from aegis.application.audit.append_audit import AppendAudit
from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.application.gateway.rate_limit import (
    REASON_RATE_LIMITED,
    REASON_RATE_UNAVAILABLE,
    RateLimiter,
    ToolRateLimits,
)
from aegis.config.settings import Settings
from aegis.domain.gateway.enums import GatewayVerdict
from aegis.domain.gateway.request import ToolInvokeRequest

_INC_A = "11111111-1111-1111-1111-111111111111"
_INC_B = "22222222-2222-2222-2222-222222222222"


def _limits(
    *,
    per_tool_incident: int = 2,
    per_agent: int = 90,
    fail_closed: bool = False,
) -> ToolRateLimits:
    return ToolRateLimits(
        window_seconds=60.0,
        per_tool_incident=per_tool_incident,
        per_agent=per_agent,
        fail_closed=fail_closed,
    )


def _request(
    tool_name: str = "retrieve_knowledge",
    *,
    incident_id: str = _INC_A,
    agent_id: str = "knowledge",
) -> ToolInvokeRequest:
    return ToolInvokeRequest(
        agent_id=agent_id,
        tool_name=tool_name,
        parameters={"query": "latency"},
        incident_id=incident_id,
    )


def _gateway(*, limiter: RateLimiter, audit: AppendAudit | None = None) -> InvokeTool:
    return InvokeTool(
        tools={"retrieve_knowledge": lambda _p: "ok"},
        rate_limiter=limiter,
        audit=audit,
    )


def test_nth_plus_one_call_is_denied_with_audit() -> None:
    runs: list[int] = []
    audit = AppendAudit()
    limiter = RateLimiter(limits=_limits(per_tool_incident=2, per_agent=90))

    def _retrieve(_params: dict[str, object]) -> str:
        runs.append(1)
        return "ok"

    gateway = InvokeTool(
        tools={"retrieve_knowledge": _retrieve},
        rate_limiter=limiter,
        audit=audit,
    )
    first = gateway.invoke(_request())
    second = gateway.invoke(_request())
    third = gateway.invoke(_request())

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.reason == REASON_RATE_LIMITED
    assert third.result is None
    assert len(runs) == 2
    rows = audit.log.entries
    assert len(rows) == 3
    assert rows[2].decision is GatewayVerdict.DENY
    assert rows[2].reason == REASON_RATE_LIMITED
    assert third.audit_id is not None


def test_different_incident_is_still_allowed() -> None:
    """Incident-scoped keys: one flood does not starve another investigation."""
    limiter = RateLimiter(limits=_limits(per_tool_incident=1, per_agent=90))
    gateway = _gateway(limiter=limiter)
    first = gateway.invoke(_request(incident_id=_INC_A))
    blocked = gateway.invoke(_request(incident_id=_INC_A))
    other = gateway.invoke(_request(incident_id=_INC_B))

    assert first.allowed is True
    assert blocked.reason == REASON_RATE_LIMITED
    assert other.allowed is True
    assert other.incident_id == _INC_B


def test_global_per_agent_cap_applies_across_incidents() -> None:
    limiter = RateLimiter(limits=_limits(per_tool_incident=10, per_agent=2))
    gateway = _gateway(limiter=limiter)
    assert gateway.invoke(_request(incident_id=_INC_A)).allowed is True
    assert gateway.invoke(_request(incident_id=_INC_B)).allowed is True
    denied = gateway.invoke(_request(incident_id=_INC_A))
    assert denied.allowed is False
    assert denied.reason == REASON_RATE_LIMITED


def test_store_down_fails_closed_in_production_mode() -> None:
    class _Broken:
        def try_acquire_all(self, items: Sequence[tuple[str, int, float]]) -> bool:
            raise RuntimeError("redis down")

    limiter = RateLimiter(limits=_limits(fail_closed=True), store=_Broken())
    decision = _gateway(limiter=limiter).invoke(_request())
    assert decision.allowed is False
    assert decision.reason == REASON_RATE_UNAVAILABLE


def test_store_down_fails_open_locally() -> None:
    class _Broken:
        def try_acquire_all(self, items: Sequence[tuple[str, int, float]]) -> bool:
            raise RuntimeError("redis down")

    limiter = RateLimiter(limits=_limits(fail_closed=False), store=_Broken())
    decision = _gateway(limiter=limiter).invoke(_request())
    assert decision.allowed is True
    assert decision.reason == "allowed:read"


def test_limits_come_from_settings() -> None:
    settings = Settings(
        environment="production",
        tool_rate_window_seconds=60,
        tool_rate_per_tool_incident=30,
        tool_rate_per_agent=90,
        tool_rate_fail_closed=True,
    )
    limits = ToolRateLimits.from_settings(settings)
    assert limits.per_tool_incident == 30
    assert limits.per_agent == 90
    assert limits.window_seconds == 60.0
    assert limits.fail_closed is True
    assert Settings().tool_rate_per_tool_incident == 30
