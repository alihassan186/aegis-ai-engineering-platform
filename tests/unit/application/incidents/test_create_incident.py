"""CreateIncident use case."""

from __future__ import annotations

import pytest

from aegis.application.incidents import CreateIncident, CreateIncidentCommand
from aegis.domain.incidents import IncidentState, Severity
from aegis.shared.exceptions import ValidationError
from tests.unit.application.incidents.fakes import FakeIncidentRepository


async def test_create_opens_incident_with_timestamp() -> None:
    repo = FakeIncidentRepository()
    use_case = CreateIncident(repo)

    result = await use_case.execute(
        CreateIncidentCommand(
            title="Checkout latency",
            affected_service="payments-api",
            severity=Severity.HIGH,
            description="p99 above SLO",
        )
    )

    assert result.state is IncidentState.OPEN
    assert result.title == "Checkout latency"
    assert result.affected_service == "payments-api"
    assert result.severity is Severity.HIGH
    assert result.description == "p99 above SLO"
    assert result.created_at.tzinfo is not None
    assert result.updated_at == result.created_at
    assert result.state_history == ()
    assert len(repo.created) == 1
    assert repo.created[0].id == result.id
    assert repo.created[0].state is IncidentState.OPEN


async def test_create_rejects_blank_title() -> None:
    use_case = CreateIncident(FakeIncidentRepository())

    with pytest.raises(ValidationError, match="title"):
        await use_case.execute(
            CreateIncidentCommand(
                title="  ",
                affected_service="api",
                severity=Severity.LOW,
            )
        )
