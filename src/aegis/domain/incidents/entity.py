"""Incident aggregate — identity, validation, and lifecycle rules (FR-002–FR-005).

The incident is the domain root. It has a unique id, textual details, a
lifecycle state, severity, and an affected service. State may change only
through allowed transitions; each change is timestamped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from aegis.domain.incidents.enums import IncidentState, Severity
from aegis.domain.incidents.transitions import require_allowed_transition
from aegis.shared.exceptions import ValidationError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(moment: datetime, field_name: str) -> datetime:
    if moment.tzinfo is None:
        raise ValidationError(f"{field_name} must be timezone-aware.")
    return moment


def _require_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(f"{field_name} must not be empty.")
    return cleaned


@dataclass(frozen=True, slots=True)
class StateTransition:
    """Immutable record of one lifecycle change (FR-004)."""

    from_state: IncidentState
    to_state: IncidentState
    occurred_at: datetime


class Incident:
    """Incident entity. Mutates only through domain methods."""

    def __init__(
        self,
        *,
        id: UUID,
        title: str,
        description: str | None,
        state: IncidentState,
        severity: Severity,
        affected_service: str,
        owner_id: UUID | None,
        created_at: datetime,
        updated_at: datetime,
        state_history: list[StateTransition] | None = None,
    ) -> None:
        self._id = id
        self._title = _require_text(title, "title")
        cleaned_description = description.strip() if description else ""
        self._description = cleaned_description or None
        self._state = state
        self._severity = severity
        self._affected_service = _require_text(affected_service, "affected_service")
        self._owner_id = owner_id
        self._created_at = _require_aware(created_at, "created_at")
        self._updated_at = _require_aware(updated_at, "updated_at")
        self._state_history = list(state_history or [])

    @classmethod
    def create(
        cls,
        *,
        title: str,
        affected_service: str,
        severity: Severity,
        description: str | None = None,
        owner_id: UUID | None = None,
        incident_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> Incident:
        """Open a new incident (FR-002, FR-005)."""
        moment = _require_aware(created_at, "created_at") if created_at else _utc_now()
        print(f"moment in incident.py: {moment}")
        return cls(
            id=incident_id or uuid4(),
            title=title,
            description=description,
            state=IncidentState.OPEN,
            severity=severity,
            affected_service=affected_service,
            owner_id=owner_id,
            created_at=moment,
            updated_at=moment,
            state_history=[],
        )

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str | None:
        return self._description

    @property
    def state(self) -> IncidentState:
        return self._state

    @property
    def severity(self) -> Severity:
        return self._severity

    @property
    def affected_service(self) -> str:
        return self._affected_service

    @property
    def owner_id(self) -> UUID | None:
        return self._owner_id

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def state_history(self) -> tuple[StateTransition, ...]:
        return tuple(self._state_history)

    def transition_to(
        self,
        new_state: IncidentState,
        *,
        occurred_at: datetime | None = None,
    ) -> None:
        """Move to ``new_state`` or raise ``InvalidTransitionError`` (FR-003, FR-004)."""
        require_allowed_transition(self._state, new_state)
        moment = _require_aware(occurred_at, "occurred_at") if occurred_at else _utc_now()
        self._state_history.append(
            StateTransition(
                from_state=self._state,
                to_state=new_state,
                occurred_at=moment,
            )
        )
        self._state = new_state
        self._updated_at = moment
