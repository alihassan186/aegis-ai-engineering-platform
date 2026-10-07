"""In-process tool-use guardrail (FR-060, FR-061, FR-064, FR-067, FR-074).

Synchronous. Same worker. Not a microservice. Allow/deny comes from POLICY_RULE
rows (or the in-process seed when the cache is cold). Destructive is still a
code hard-stop. High-risk write is not executed in v0.6 (Phase 8).
Agent identity is bound by the worker, never taken from tool parameters.

Step 5.9: every allowed result carries an untrusted-data envelope.
Step 5.11: ``AEGIS_GUARDRAIL_DENY_ALL`` denies every call before any other check, and
every decision is stamped with the ``policy_version`` that made it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from aegis.application.audit.append_audit import AppendAudit
from aegis.application.gateway.classify import classify
from aegis.application.gateway.rate_limit import RateLimiter
from aegis.application.gateway.untrusted import build_envelope, redact_result
from aegis.application.policy.cache import snapshot_policy_rules, snapshot_policy_version
from aegis.application.policy.evaluate import evaluate_policy
from aegis.application.policy.seed import seed_read_rules
from aegis.application.policy.version import policy_version_for
from aegis.config.settings import guardrail_deny_all_enabled
from aegis.domain.audit.entity import AuditEntry
from aegis.domain.auth.agent_identity import AgentIdentity, agent_may_invoke, parse_agent_identity
from aegis.domain.gateway.decision import GatewayDecision
from aegis.domain.gateway.enums import ActionClass
from aegis.domain.gateway.request import ToolInvokeRequest
from aegis.domain.policy.entity import PolicyRule
from aegis.shared.exceptions import ValidationError

logger = logging.getLogger("aegis.guardrail")

ToolFn = Callable[[Mapping[str, Any]], Any]


class InvokeTool:
    """``ToolGateway`` implementation: identity → classify → policy → maybe run."""

    def __init__(
        self,
        tools: Mapping[str, ToolFn] | None = None,
        *,
        policy_rules: Sequence[PolicyRule] | None = None,
        bound_agent_id: str | AgentIdentity | None = None,
        audit: AppendAudit | None = None,
        rate_limiter: RateLimiter | None = None,
        deny_all: Callable[[], bool] | None = None,
    ) -> None:
        self._deny_all = deny_all or guardrail_deny_all_enabled
        self._tools = dict(tools or {})
        self._policy_rules = None if policy_rules is None else tuple(policy_rules)
        self._bound_agent_id = _optional_identity(bound_agent_id)
        self._audit = audit or AppendAudit()
        self._rate_limiter = rate_limiter or RateLimiter()

    def bind(self, agent_id: str | AgentIdentity) -> InvokeTool:
        """Return a gateway whose identity is closed over by a node (FR-074)."""
        identity = _require_identity(agent_id)
        return InvokeTool(
            tools=self._tools,
            policy_rules=self._policy_rules,
            bound_agent_id=identity,
            audit=self._audit,
            rate_limiter=self._rate_limiter,
            deny_all=self._deny_all,
        )

    @property
    def bound_agent_id(self) -> str | None:
        return self._bound_agent_id

    def invoke(self, request: ToolInvokeRequest) -> GatewayDecision:
        action_class = classify(request.tool_name)
        _ = request.claimed_action_class  # ignored — model cannot self-authorize
        deny_all = bool(self._deny_all())
        decision = self._decide(request, action_class, deny_all=deny_all)
        decision = decision.with_governance(
            policy_version=self._policy_version(),
            deny_all=deny_all,
        )
        entry = self._audit.record_decision(request, decision)
        decision = decision.with_audit_id(str(entry.id))
        logger.info(
            "guardrail %s tool=%s reason=%s audit_id=%s",
            "allow" if decision.allowed else "deny",
            request.tool_name,
            decision.reason,
            decision.audit_id,
            extra={
                "incident_id": request.incident_id,
                "agent_id": decision.agent_id,
                "tool_name": request.tool_name,
                "reason": decision.reason,
                "audit_id": decision.audit_id,
            },
        )
        return decision

    def drain_audit(self) -> list[AuditEntry]:
        return self._audit.drain()

    def execute(self, request: ToolInvokeRequest) -> GatewayDecision:
        return self.invoke(request)

    def _active_rules(self) -> Sequence[PolicyRule]:
        if self._policy_rules is not None:
            return self._policy_rules
        cached = snapshot_policy_rules()
        if cached is not None:
            return cached
        return seed_read_rules()

    def _policy_version(self) -> str:
        if self._policy_rules is not None:
            return policy_version_for(self._policy_rules)
        cached = snapshot_policy_version()
        if cached is not None:
            return cached
        return policy_version_for(seed_read_rules())

    def _caller_identity(self, request: ToolInvokeRequest) -> str:
        """Bound identity wins. ``parameters['agent_id']`` is never consulted."""
        if self._bound_agent_id is not None:
            return self._bound_agent_id
        return request.agent_id

    def _decide(
        self,
        request: ToolInvokeRequest,
        action_class: ActionClass | None,
        *,
        deny_all: bool = False,
    ) -> GatewayDecision:
        agent_id = self._caller_identity(request)
        parameters = _tool_parameters(request)
        common = {
            "tool_name": request.tool_name,
            "agent_id": agent_id,
            "incident_id": request.incident_id,
        }
        if deny_all:
            # Break-glass (5.11): env only. Never a tool parameter, comment, or prompt.
            return GatewayDecision.deny(
                reason="denied:kill_switch",
                action_class=action_class,
                **common,
            )
        if parse_agent_identity(agent_id) is None:
            return GatewayDecision.deny(
                reason="denied:unknown_agent",
                action_class=action_class,
                **common,
            )
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
        if action_class is not None and not agent_may_invoke(agent_id, request.tool_name):
            return GatewayDecision.deny(
                reason="denied:agent_scope",
                action_class=action_class,
                **common,
            )

        service = str(parameters.get("service") or "")
        verdict = evaluate_policy(
            self._active_rules(),
            tool_name=request.tool_name,
            action_class=action_class,
            agent_id=agent_id,
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
        paced = self._rate_limiter.allow(
            agent_id=agent_id,
            tool_name=request.tool_name,
            incident_id=request.incident_id,
        )
        if not paced.allowed:
            return GatewayDecision.deny(
                reason=paced.reason,
                action_class=resolved,
                **common,
            )
        try:
            raw = runner(parameters)
        except ValidationError as exc:
            reason = str(exc)
            if not reason.startswith("denied:"):
                reason = "denied:invalid_params"
            return GatewayDecision.deny(
                reason=reason,
                action_class=resolved,
                **common,
            )
        except Exception as exc:  # fail closed, and still audit (5.10)
            logger.warning(
                "tool runner failed tool=%s error=%s",
                request.tool_name,
                type(exc).__name__,
            )
            return GatewayDecision.deny(
                reason="denied:tool_error",
                action_class=resolved,
                **common,
            )
        truncated = bool(getattr(raw, "truncated", False))
        result = redact_result(raw)
        envelope = build_envelope(
            tool_name=request.tool_name,
            incident_id=request.incident_id,
            result=result,
            truncated=truncated,
        )
        return GatewayDecision.allow(
            reason="allowed:read",
            action_class=resolved,
            result=result,
            envelope=envelope.as_dict(),
            **common,
        )


def _optional_identity(value: str | AgentIdentity | None) -> str | None:
    if value is None:
        return None
    return _require_identity(value)


def _require_identity(value: str | AgentIdentity) -> str:
    if isinstance(value, AgentIdentity):
        return value.value
    identity = parse_agent_identity(str(value))
    if identity is None:
        raise ValidationError(f"unknown agent_id '{value}'.")
    return identity.value


def _tool_parameters(request: ToolInvokeRequest) -> dict[str, Any]:
    """Drop identity claims. The model cannot mint ``agent_id`` via params."""
    params = request.parameters
    params.pop("agent_id", None)
    params.pop("action_class", None)
    return params
