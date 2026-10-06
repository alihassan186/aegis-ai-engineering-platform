"""Append a redacted gateway decision to the audit log (FR-062, FR-100)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from aegis.application.audit.memory import MemoryAuditRepository
from aegis.application.security.redact import redact_mapping
from aegis.core.protocols import AuditRepository
from aegis.domain.audit.entity import GENESIS_HASH, AuditEntry
from aegis.domain.gateway.decision import GatewayDecision
from aegis.domain.gateway.enums import GatewayVerdict
from aegis.domain.gateway.request import ToolInvokeRequest


class AppendAudit:
    """Redact, then append. Never logs the pre-image."""

    def __init__(self, log: MemoryAuditRepository | None = None) -> None:
        self._log = log or MemoryAuditRepository()

    @property
    def log(self) -> MemoryAuditRepository:
        return self._log

    def record_decision(
        self,
        request: ToolInvokeRequest,
        decision: GatewayDecision,
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> AuditEntry:
        """Sync path used by ``InvokeTool``. Denies are recorded too."""
        entry = self._build(
            request=request,
            decision=decision,
            parameters=parameters,
            prev_hash=self._log.latest_hash_sync(),
        )
        return self._log.append_sync(entry)

    async def execute(
        self,
        *,
        repository: AuditRepository,
        actor: str,
        action: str,
        incident_id: str,
        decision: GatewayVerdict | str,
        reason: str,
        input: Mapping[str, Any],
        output: Mapping[str, Any] | None = None,
        action_class: str | None = None,
    ) -> AuditEntry:
        """Async persist path (worker flush / integration tests)."""
        prev = await repository.latest_hash()
        entry = AuditEntry.create(
            actor=actor,
            action=action,
            input=_redact_json(input),
            output=None if output is None else _redact_json(output),
            decision=decision,
            reason=reason,
            incident_id=incident_id,
            action_class=action_class,
            prev_hash=prev or GENESIS_HASH,
        )
        return await repository.append(entry)

    async def persist(self, repository: AuditRepository, entry: AuditEntry) -> AuditEntry:
        return await repository.append(entry)

    def drain(self) -> list[AuditEntry]:
        return self._log.drain()

    def _build(
        self,
        *,
        request: ToolInvokeRequest,
        decision: GatewayDecision,
        parameters: Mapping[str, Any] | None,
        prev_hash: str,
    ) -> AuditEntry:
        params = dict(parameters if parameters is not None else request.parameters)
        params.pop("agent_id", None)
        params.pop("action_class", None)
        if decision.allowed:
            output: dict[str, Any] | None = _wrap_output(decision.result)
        else:
            output = {"error": decision.error or decision.reason}
        return AuditEntry.create(
            actor=decision.agent_id or request.agent_id,
            action=decision.tool_name or request.tool_name,
            input=_redact_json(params),
            output=_redact_json(output),
            decision=decision.verdict,
            reason=decision.reason,
            incident_id=decision.incident_id or request.incident_id,
            action_class=None if decision.action_class is None else decision.action_class.value,
            prev_hash=prev_hash,
        )


def _redact_json(value: Any) -> dict[str, Any]:
    redacted, _count = redact_mapping(value)
    if isinstance(redacted, Mapping):
        return dict(redacted)
    return {"value": redacted}


def _wrap_output(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value is None:
        return {}
    return {"value": value}


def parse_audit_id(raw: str | None) -> UUID | None:
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None
