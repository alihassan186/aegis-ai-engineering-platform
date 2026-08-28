"""ORM ↔ domain mapping. Application code must never import these models."""

from __future__ import annotations

from uuid import UUID, uuid4

from aegis.domain.incidents.entity import Incident, StateTransition
from aegis.domain.incidents.enums import IncidentState, Severity
from aegis.infrastructure.database.models.incident import IncidentModel
from aegis.infrastructure.database.models.state_history import IncidentStateHistoryModel


def to_domain(row: IncidentModel) -> Incident:
    history = [
        StateTransition(
            from_state=IncidentState(entry.from_state),
            to_state=IncidentState(entry.to_state),
            occurred_at=entry.transitioned_at,
        )
        for entry in row.state_history
    ]
    return Incident(
        id=row.id,
        title=row.title,
        description=row.description,
        state=IncidentState(row.state),
        severity=Severity(row.severity),
        affected_service=row.affected_service,
        owner_id=row.owner_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        state_history=history,
    )


def to_orm(incident: Incident) -> IncidentModel:
    row = IncidentModel(
        id=incident.id,
        title=incident.title,
        description=incident.description,
        state=incident.state.value,
        severity=incident.severity.value,
        affected_service=incident.affected_service,
        owner_id=incident.owner_id,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        deleted_at=None,
    )
    row.state_history = [_history_row(incident.id, step) for step in incident.state_history]
    return row


def apply_to_orm(incident: Incident, row: IncidentModel) -> None:
    """Copy domain state onto an existing row, appending new history only."""
    row.title = incident.title
    row.description = incident.description
    row.state = incident.state.value
    row.severity = incident.severity.value
    row.affected_service = incident.affected_service
    row.owner_id = incident.owner_id
    row.updated_at = incident.updated_at

    existing = {
        (entry.from_state, entry.to_state, entry.transitioned_at) for entry in row.state_history
    }
    for step in incident.state_history:
        key = (step.from_state.value, step.to_state.value, step.occurred_at)
        if key not in existing:
            row.state_history.append(_history_row(incident.id, step))


def _history_row(incident_id: UUID, step: StateTransition) -> IncidentStateHistoryModel:
    return IncidentStateHistoryModel(
        id=uuid4(),
        incident_id=incident_id,
        from_state=step.from_state.value,
        to_state=step.to_state.value,
        transitioned_at=step.occurred_at,
    )
