"""Outbound guardrail contract (system boundaries §4)."""

from __future__ import annotations

from typing import Any

from aegis.domain.gateway.enums import ActionClass, GatewayVerdict


class GatewayDecision:
    """Allow / deny / pending plus optional redacted result."""

    def __init__(
        self,
        *,
        allowed: bool,
        reason: str,
        requires_approval: bool,
        verdict: GatewayVerdict,
        action_class: ActionClass | None,
        result: Any = None,
        error: str | None = None,
        audit_id: str | None = None,
        tool_name: str = "",
        agent_id: str = "",
        incident_id: str = "",
    ) -> None:
        self._allowed = allowed
        self._reason = reason
        self._requires_approval = requires_approval
        self._verdict = verdict
        self._action_class = action_class
        self._result = result
        self._error = error
        self._audit_id = audit_id
        self._tool_name = tool_name
        self._agent_id = agent_id
        self._incident_id = incident_id

    @classmethod
    def allow(
        cls,
        *,
        reason: str,
        action_class: ActionClass,
        result: Any,
        tool_name: str,
        agent_id: str,
        incident_id: str,
    ) -> GatewayDecision:
        return cls(
            allowed=True,
            reason=reason,
            requires_approval=False,
            verdict=GatewayVerdict.ALLOW,
            action_class=action_class,
            result=result,
            tool_name=tool_name,
            agent_id=agent_id,
            incident_id=incident_id,
        )

    @classmethod
    def deny(
        cls,
        *,
        reason: str,
        action_class: ActionClass | None,
        tool_name: str,
        agent_id: str,
        incident_id: str,
        requires_approval: bool = False,
        error: str | None = None,
    ) -> GatewayDecision:
        verdict = GatewayVerdict.PENDING if requires_approval else GatewayVerdict.DENY
        return cls(
            allowed=False,
            reason=reason,
            requires_approval=requires_approval,
            verdict=verdict,
            action_class=action_class,
            error=error or reason,
            tool_name=tool_name,
            agent_id=agent_id,
            incident_id=incident_id,
        )

    @property
    def allowed(self) -> bool:
        return self._allowed

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def requires_approval(self) -> bool:
        return self._requires_approval

    @property
    def verdict(self) -> GatewayVerdict:
        return self._verdict

    @property
    def action_class(self) -> ActionClass | None:
        return self._action_class

    @property
    def result(self) -> Any:
        return self._result

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def audit_id(self) -> str | None:
        return self._audit_id

    @property
    def tool_name(self) -> str:
        return self._tool_name

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def incident_id(self) -> str:
        return self._incident_id
