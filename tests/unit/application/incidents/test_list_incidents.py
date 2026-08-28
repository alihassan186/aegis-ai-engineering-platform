"""ListIncidents maps FR-009 filters onto the repository port."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from aegis.application.incidents import (
    CreateIncident,
    CreateIncidentCommand,
    ListIncidents,
    ListIncidentsQuery,
)
from aegis.core.protocols import IncidentFilters
from aegis.domain.incidents import IncidentState, Severity
from tests.unit.application.incidents.fakes import FakeIncidentRepository


async def test_list_passes_all_fr009_filters_to_repository() -> None:
    repo = FakeIncidentRepository()
    owner_id = uuid4()
    created_after = datetime(2026, 8, 1, tzinfo=UTC)
    created_before = datetime(2026, 8, 31, tzinfo=UTC)

    await ListIncidents(repo).execute(
        ListIncidentsQuery(
            state=IncidentState.INVESTIGATING,
            severity=Severity.CRITICAL,
            affected_service="payments-api",
            owner_id=owner_id,
            created_after=created_after,
            created_before=created_before,
        )
    )

    assert repo.last_filters == IncidentFilters(
        state=IncidentState.INVESTIGATING,
        severity=Severity.CRITICAL,
        affected_service="payments-api",
        owner_id=owner_id,
        created_after=created_after,
        created_before=created_before,
    )


async def test_list_returns_dtos_from_repository() -> None:
    repo = FakeIncidentRepository()
    created = await CreateIncident(repo).execute(
        CreateIncidentCommand(
            title="API errors",
            affected_service="checkout-api",
            severity=Severity.HIGH,
        )
    )

    results = await ListIncidents(repo).execute(ListIncidentsQuery())

    assert [item.id for item in results] == [created.id]
    assert results[0].title == "API errors"
