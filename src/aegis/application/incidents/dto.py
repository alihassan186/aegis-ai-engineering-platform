"""Application-level incident commands, queries, and read models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aegis.domain.incidents.entity import Incident
from aegis.domain.incidents.enums import IncidentState, Severity


@dataclass(frozen=True, slots=True)
class CreateIncidentCommand:
    title: str
    affected_service: str
    severity: Severity
    description: str | None = None
    owner_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class IngestIncidentSignalCommand:
    """Inbound incident.signal.v1 mapped onto CreateIncident fields (FR-113)."""

    source: str
    service: str
    title: str
    severity: Severity
    summary: str | None = None
    scenario: str | None = None
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class ListIncidentsQuery:
    state: IncidentState | None = None
    severity: Severity | None = None
    affected_service: str | None = None
    owner_id: UUID | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


@dataclass(frozen=True, slots=True)
class TransitionIncidentCommand:
    incident_id: UUID
    new_state: IncidentState


@dataclass(frozen=True, slots=True)
class StateTransitionDto:
    from_state: IncidentState
    to_state: IncidentState
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class IncidentDto:
    id: UUID
    title: str
    description: str | None
    state: IncidentState
    severity: Severity
    affected_service: str
    owner_id: UUID | None
    created_at: datetime
    updated_at: datetime
    state_history: tuple[StateTransitionDto, ...]

    @classmethod
    def from_entity(cls, incident: Incident) -> IncidentDto:
        return cls(
            id=incident.id,
            title=incident.title,
            description=incident.description,
            state=incident.state,
            severity=incident.severity,
            affected_service=incident.affected_service,
            owner_id=incident.owner_id,
            created_at=incident.created_at,
            updated_at=incident.updated_at,
            state_history=tuple(
                StateTransitionDto(
                    from_state=step.from_state,
                    to_state=step.to_state,
                    occurred_at=step.occurred_at,
                )
                for step in incident.state_history
            ),
        )
