"""POLICY_RULE as data. Admins change scope without a worker image (FR-066)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from aegis.domain.gateway.enums import ActionClass
from aegis.shared.exceptions import ValidationError

WILDCARD = "*"
_MAX_TOOL = 128
_MAX_SCOPE = 255
_MAX_REASON = 255
_MAX_ACTOR = 128


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


def _parse_action_class(value: ActionClass | str) -> ActionClass:
    if isinstance(value, ActionClass):
        return value
    try:
        return ActionClass(value.strip())
    except ValueError as exc:
        raise ValidationError(
            "action_class must be read, low-risk-write, high-risk-write, or destructive."
        ) from exc


class PolicyRule:
    """One allow/deny row. ``tool_name`` and ``scope`` may be ``*``."""

    def __init__(
        self,
        *,
        id: UUID,
        tool_name: str,
        action_class: ActionClass,
        scope: str,
        allowed: bool,
        reason: str,
        created_by: str,
        updated_by: str,
        created_at: datetime,
        updated_at: datetime,
        version: int = 1,
    ) -> None:
        if version < 1:
            raise ValidationError("version must be at least 1.")
        self._version = int(version)
        self._id = id
        self._tool_name = _require_token(tool_name, "tool_name", max_length=_MAX_TOOL)
        self._action_class = action_class
        self._scope = _require_token(scope, "scope", max_length=_MAX_SCOPE)
        self._allowed = bool(allowed)
        self._reason = reason.strip()
        if len(self._reason) > _MAX_REASON:
            raise ValidationError(f"reason must be at most {_MAX_REASON} characters.")
        self._created_by = _require_token(created_by, "created_by", max_length=_MAX_ACTOR)
        self._updated_by = _require_token(updated_by, "updated_by", max_length=_MAX_ACTOR)
        self._created_at = _require_aware(created_at, "created_at")
        self._updated_at = _require_aware(updated_at, "updated_at")
        if self._allowed and self._action_class is ActionClass.DESTRUCTIVE:
            raise ValidationError("destructive tools cannot be allowed by a policy rule.")

    @classmethod
    def create(
        cls,
        *,
        tool_name: str,
        action_class: ActionClass | str,
        scope: str,
        allowed: bool,
        actor: str,
        reason: str = "",
        rule_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> PolicyRule:
        now = created_at or _utc_now()
        who = _require_token(actor, "actor", max_length=_MAX_ACTOR)
        return cls(
            id=rule_id or uuid4(),
            tool_name=tool_name,
            action_class=_parse_action_class(action_class),
            scope=scope,
            allowed=allowed,
            reason=reason,
            created_by=who,
            updated_by=who,
            created_at=now,
            updated_at=now,
        )

    def replace(
        self,
        *,
        actor: str,
        tool_name: str | None = None,
        action_class: ActionClass | str | None = None,
        scope: str | None = None,
        allowed: bool | None = None,
        reason: str | None = None,
        updated_at: datetime | None = None,
    ) -> PolicyRule:
        who = _require_token(actor, "actor", max_length=_MAX_ACTOR)
        return PolicyRule(
            id=self._id,
            tool_name=self._tool_name if tool_name is None else tool_name,
            action_class=(
                self._action_class if action_class is None else _parse_action_class(action_class)
            ),
            scope=self._scope if scope is None else scope,
            allowed=self._allowed if allowed is None else allowed,
            reason=self._reason if reason is None else reason,
            created_by=self._created_by,
            updated_by=who,
            created_at=self._created_at,
            updated_at=updated_at or _utc_now(),
            version=self._version + 1,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": str(self._id),
            "tool_name": self._tool_name,
            "action_class": self._action_class.value,
            "scope": self._scope,
            "allowed": self._allowed,
            "reason": self._reason,
            "created_by": self._created_by,
            "updated_by": self._updated_by,
            "version": self._version,
        }

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def version(self) -> int:
        """Per-rule edit counter. Bumped on every admin ``replace`` (5.11)."""
        return self._version

    @property
    def tool_name(self) -> str:
        return self._tool_name

    @property
    def action_class(self) -> ActionClass:
        return self._action_class

    @property
    def scope(self) -> str:
        return self._scope

    @property
    def allowed(self) -> bool:
        return self._allowed

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def created_by(self) -> str:
        return self._created_by

    @property
    def updated_by(self) -> str:
        return self._updated_by

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at


class PolicyRuleChange:
    """Who changed which rule, before 5.6 immutable audit (THR-004 lite)."""

    def __init__(
        self,
        *,
        id: UUID,
        rule_id: UUID | None,
        actor: str,
        action: str,
        before: Mapping[str, Any] | None,
        after: Mapping[str, Any] | None,
        created_at: datetime,
    ) -> None:
        cleaned = action.strip()
        if cleaned not in {"created", "updated", "deleted"}:
            raise ValidationError("action must be created, updated, or deleted.")
        self._id = id
        self._rule_id = rule_id
        self._actor = _require_token(actor, "actor", max_length=_MAX_ACTOR)
        self._action = cleaned
        self._before = dict(before) if before is not None else None
        self._after = dict(after) if after is not None else None
        self._created_at = _require_aware(created_at, "created_at")

    @classmethod
    def record(
        cls,
        *,
        actor: str,
        action: str,
        rule_id: UUID | None,
        before: Mapping[str, Any] | None,
        after: Mapping[str, Any] | None,
        change_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> PolicyRuleChange:
        return cls(
            id=change_id or uuid4(),
            rule_id=rule_id,
            actor=actor,
            action=action,
            before=before,
            after=after,
            created_at=created_at or _utc_now(),
        )

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def rule_id(self) -> UUID | None:
        return self._rule_id

    @property
    def actor(self) -> str:
        return self._actor

    @property
    def action(self) -> str:
        return self._action

    @property
    def before(self) -> dict[str, Any] | None:
        return None if self._before is None else dict(self._before)

    @property
    def after(self) -> dict[str, Any] | None:
        return None if self._after is None else dict(self._after)

    @property
    def created_at(self) -> datetime:
        return self._created_at
