"""GetIncident use case."""

from __future__ import annotations

from uuid import uuid4

import pytest

from aegis.application.incidents import CreateIncident, CreateIncidentCommand, GetIncident
from aegis.domain.incidents import Severity
from aegis.shared.exceptions import NotFoundError
from tests.unit.application.incidents.fakes import FakeIncidentRepository


async def test_get_returns_persisted_incident() -> None:
    repo = FakeIncidentRepository()
    created = await CreateIncident(repo).execute(
        CreateIncidentCommand(
            title="Disk full",
            affected_service="worker",
            severity=Severity.MEDIUM,
        )
    )

    loaded = await GetIncident(repo).execute(created.id)

    assert loaded.id == created.id
    assert loaded.title == "Disk full"


async def test_get_missing_incident_raises_not_found() -> None:
    use_case = GetIncident(FakeIncidentRepository())

    with pytest.raises(NotFoundError, match="was not found"):
        await use_case.execute(uuid4())
