"""TransitionIncident delegates lifecycle rules to the domain."""

from __future__ import annotations

from uuid import uuid4

import pytest

from aegis.application.incidents import (
    CreateIncident,
    CreateIncidentCommand,
    TransitionIncident,
    TransitionIncidentCommand,
)
from aegis.domain.incidents import IncidentState, InvalidTransitionError, Severity
from aegis.shared.exceptions import NotFoundError
from tests.unit.application.incidents.fakes import FakeIncidentRepository


async def _open_incident(repo: FakeIncidentRepository):
    return await CreateIncident(repo).execute(
        CreateIncidentCommand(
            title="Checkout latency",
            affected_service="payments-api",
            severity=Severity.HIGH,
        )
    )


async def test_transition_open_to_investigating_records_history() -> None:
    repo = FakeIncidentRepository()
    created = await _open_incident(repo)

    result = await TransitionIncident(repo).execute(
        TransitionIncidentCommand(
            incident_id=created.id,
            new_state=IncidentState.INVESTIGATING,
        )
    )

    assert result.state is IncidentState.INVESTIGATING
    assert len(result.state_history) == 1
    assert result.state_history[0].from_state is IncidentState.OPEN
    assert result.state_history[0].to_state is IncidentState.INVESTIGATING
    assert result.state_history[0].occurred_at.tzinfo is not None
    assert result.updated_at == result.state_history[0].occurred_at
    assert len(repo.saved) == 1
    assert repo.saved[0].state is IncidentState.INVESTIGATING


async def test_transition_open_to_resolved_is_rejected() -> None:
    repo = FakeIncidentRepository()
    created = await _open_incident(repo)

    with pytest.raises(InvalidTransitionError):
        await TransitionIncident(repo).execute(
            TransitionIncidentCommand(
                incident_id=created.id,
                new_state=IncidentState.RESOLVED,
            )
        )

    assert repo.saved == []
    assert repo.items[created.id].state is IncidentState.OPEN


async def test_transition_missing_incident_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        await TransitionIncident(FakeIncidentRepository()).execute(
            TransitionIncidentCommand(
                incident_id=uuid4(),
                new_state=IncidentState.INVESTIGATING,
            )
        )
