"""In-process tool-use guardrail (FR-060, FR-061, FR-064, FR-067).

Synchronous. Same worker. Not a microservice. Allow/deny comes from POLICY_RULE
rows (or the in-process seed when the cache is cold). Destructive is still a
code hard-stop. High-risk write is not executed in v0.6 (Phase 8).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from aegis.application.gateway.classify import classify
from aegis.application.policy.cache import snapshot_policy_rules
from aegis.application.policy.evaluate import evaluate_policy
from aegis.application.policy.seed import seed_read_rules
from aegis.application.security.redact import redact_for_llm, redact_mapping
from aegis.domain.gateway.decision import GatewayDecision
from aegis.domain.gateway.enums import ActionClass
from aegis.domain.gateway.request import ToolInvokeRequest
from aegis.domain.policy.entity import PolicyRule

logger = logging.getLogger("aegis.guardrail")

ToolFn = Callable[[Mapping[str, Any]], Any]


class InvokeTool:
    """``ToolGateway`` implementation: classify → policy → maybe run."""

    def __init__(
        self,
        tools: Mapping[str, ToolFn] | None = None,
        *,
        policy_rules: Sequence[PolicyRule] | None = None,
    ) -> None:
        self._tools = dict(tools or {})
        self._policy_rules = None if policy_rules is None else tuple(policy_rules)

    def invoke(self, request: ToolInvokeRequest) -> GatewayDecision:
        action_class = classify(request.tool_name)
        _ = request.claimed_action_class  # ignored — model cannot self-authorize
        decision = self._decide(request, action_class)
        logger.info(
            "guardrail %s tool=%s reason=%s",
            "allow" if decision.allowed else "deny",
            request.tool_name,
            decision.reason,
            extra={
                "incident_id": request.incident_id,
                "agent_id": request.agent_id,
                "tool_name": request.tool_name,
                "reason": decision.reason,
            },
        )
        return decision

    def execute(self, request: ToolInvokeRequest) -> GatewayDecision:
        return self.invoke(request)

    def _active_rules(self) -> Sequence[PolicyRule]:
        if self._policy_rules is not None:
            return self._policy_rules
        cached = snapshot_policy_rules()
        if cached is not None:
            return cached
        return seed_read_rules()

    def _decide(
        self,
        request: ToolInvokeRequest,
        action_class: ActionClass | None,
    ) -> GatewayDecision:
        common = {
            "tool_name": request.tool_name,
            "agent_id": request.agent_id,
            "incident_id": request.incident_id,
        }
        if action_class is ActionClass.DESTRUCTIVE:
            return GatewayDecision.deny(
                reason="denied:destructive",
                action_class=action_class,
                **common,
            )
        if action_class is ActionClass.HIGH_RISK_WRITE:
            return GatewayDecision.deny(
                reason="denied:high_risk_write",
                action_class=action_class,
                requires_approval=True,
                **common,
            )
        if action_class is ActionClass.LOW_RISK_WRITE:
            return GatewayDecision.deny(
                reason="denied:low_risk_write",
                action_class=action_class,
                **common,
            )

        service = str(request.parameters.get("service") or "")
        verdict = evaluate_policy(
            self._active_rules(),
            tool_name=request.tool_name,
            action_class=action_class,
            agent_id=request.agent_id,
            service=service,
        )
        resolved = action_class or verdict.action_class
        if not verdict.allowed:
            return GatewayDecision.deny(
                reason=verdict.reason,
                action_class=resolved,
                **common,
            )
        if resolved is not ActionClass.READ:
            return GatewayDecision.deny(
                reason="denied:unknown_tool",
                action_class=resolved,
                **common,
            )

        runner = self._tools.get(request.tool_name)
        if runner is None:
            return GatewayDecision.deny(
                reason="denied:not_registered",
                action_class=resolved,
                **common,
            )
        raw = runner(request.parameters)
        return GatewayDecision.allow(
            reason="allowed:read",
            action_class=resolved,
            result=_redact_result(raw),
            **common,
        )


def _redact_result(value: Any) -> Any:
    if isinstance(value, str):
        return redact_for_llm(value)
    if isinstance(value, Mapping):
        redacted, _count = redact_mapping(value)
        return redacted
    if isinstance(value, list):
        redacted, _count = redact_mapping(value)
        return redacted
    return value
