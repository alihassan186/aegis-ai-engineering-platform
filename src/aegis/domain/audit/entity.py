"""Immutable AUDIT_LOG row (FR-100, FR-062, THR-004).

This is a compliance record, not an application log line. Rows are appended
and never updated. Inputs/outputs must already be redacted before create.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from aegis.domain.gateway.enums import ActionClass, GatewayVerdict
from aegis.shared.exceptions import ValidationError

GENESIS_HASH = "0" * 64
_MAX_ACTOR = 128
_MAX_ACTION = 128
_MAX_REASON = 255
_MAX_INCIDENT = 64


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(moment: datetime, field_name: str) -> datetime:
    if moment.tzinfo is None:
        raise ValidationError(f"{field_name} must be timezone-aware.")
    return moment


def _require_token(value: str, field_name: str, *, max_length: int) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(f"{field_name} must not be empty.")
    if len(cleaned) > max_length:
        raise ValidationError(f"{field_name} must be at most {max_length} characters.")
    return cleaned


def compute_row_hash(*, payload: Mapping[str, Any], prev_hash: str) -> str:
    """SHA-256 over canonical JSON + previous digest (tamper evidence)."""
    body = {**dict(payload), "prev_hash": prev_hash}
    blob = json.dumps(body, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class AuditEntry:
    """One gateway decision. No setters — replace the object, never the row."""

    def __init__(
        self,
        *,
        id: UUID,
        actor: str,
        action: str,
        input: Mapping[str, Any],
        output: Mapping[str, Any] | None,
        decision: GatewayVerdict,
        reason: str,
        incident_id: str,
        action_class: ActionClass | None,
        created_at: datetime,
        prev_hash: str,
        row_hash: str,
    ) -> None:
        self._id = id
        self._actor = _require_token(actor, "actor", max_length=_MAX_ACTOR)
        self._action = _require_token(action, "action", max_length=_MAX_ACTION)
        self._input = dict(input)
        self._output = None if output is None else dict(output)
        self._decision = decision
        self._reason = reason.strip()
        if len(self._reason) > _MAX_REASON:
            raise ValidationError(f"reason must be at most {_MAX_REASON} characters.")
        self._incident_id = _require_token(incident_id, "incident_id", max_length=_MAX_INCIDENT)
        self._action_class = action_class
        self._created_at = _require_aware(created_at, "created_at")
        self._prev_hash = _require_token(prev_hash, "prev_hash", max_length=64)
        self._row_hash = _require_token(row_hash, "row_hash", max_length=64)
        if len(self._row_hash) != 64:
            raise ValidationError("row_hash must be a SHA-256 hex digest.")

    @classmethod
    def create(
        cls,
        *,
        actor: str,
        action: str,
        input: Mapping[str, Any],
        output: Mapping[str, Any] | None,
        decision: GatewayVerdict | str,
        reason: str,
        incident_id: str,
        action_class: ActionClass | str | None = None,
        prev_hash: str = GENESIS_HASH,
        entry_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> AuditEntry:
        verdict = decision if isinstance(decision, GatewayVerdict) else GatewayVerdict(decision)
        resolved_class = None
        if action_class is not None:
            resolved_class = (
                action_class if isinstance(action_class, ActionClass) else ActionClass(action_class)
            )
        entry_id = entry_id or uuid4()
        created_at = created_at or _utc_now()
        chain_prev = prev_hash.strip() or GENESIS_HASH
        payload = {
            "id": str(entry_id),
            "actor": actor.strip(),
            "action": action.strip(),
            "input": dict(input),
            "output": None if output is None else dict(output),
            "decision": verdict.value,
            "reason": reason.strip(),
            "incident_id": incident_id.strip(),
            "action_class": None if resolved_class is None else resolved_class.value,
            "created_at": created_at.isoformat(),
        }
        return cls(
            id=entry_id,
            actor=actor,
            action=action,
            input=input,
            output=output,
            decision=verdict,
            reason=reason,
            incident_id=incident_id,
            action_class=resolved_class,
            created_at=created_at,
            prev_hash=chain_prev,
            row_hash=compute_row_hash(payload=payload, prev_hash=chain_prev),
        )

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def actor(self) -> str:
        return self._actor

    @property
    def action(self) -> str:
        return self._action

    @property
    def input(self) -> dict[str, Any]:
        return dict(self._input)

    @property
    def output(self) -> dict[str, Any] | None:
        return None if self._output is None else dict(self._output)

    @property
    def decision(self) -> GatewayVerdict:
        return self._decision

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def incident_id(self) -> str:
        return self._incident_id

    @property
    def action_class(self) -> ActionClass | None:
        return self._action_class

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def prev_hash(self) -> str:
        return self._prev_hash

    @property
    def row_hash(self) -> str:
        return self._row_hash
