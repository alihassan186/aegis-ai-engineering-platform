"""Incident repository persists domain aggregates to PostgreSQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.core.protocols import IncidentFilters
from aegis.domain.incidents import Incident, IncidentState, Severity
from aegis.infrastructure.database.models.incident import IncidentModel
from aegis.infrastructure.repositories.incident_repository import SqlAlchemyIncidentRepository
from aegis.shared.exceptions import NotFoundError


def _incident(
    *,
    title: str = "Checkout latency",
    affected_service: str = "payments-api",
    severity: Severity = Severity.HIGH,
    description: str | None = "p99 above SLO",
    owner_id: UUID | None = None,
    created_at: datetime | None = None,
    fingerprint: str | None = None,
) -> Incident:
    return Incident.create(
        title=title,
        affected_service=affected_service,
        severity=severity,
        description=description,
        owner_id=owner_id,
        created_at=created_at,
        fingerprint=fingerprint,
    )


async def test_create_and_get_round_trips_domain_fields(db_session: AsyncSession) -> None:
    owner_id = uuid4()
    created_at = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
    incident = _incident(owner_id=owner_id, created_at=created_at)
    repo = SqlAlchemyIncidentRepository(db_session)

    await repo.create(incident)
    loaded = await repo.get_by_id(incident.id)

    assert loaded is not None
    assert loaded.id == incident.id
    assert loaded.title == "Checkout latency"
    assert loaded.description == "p99 above SLO"
    assert loaded.state is IncidentState.OPEN
    assert loaded.severity is Severity.HIGH
    assert loaded.affected_service == "payments-api"
    assert loaded.owner_id == owner_id
    assert loaded.created_at == created_at
    assert loaded.state_history == ()


async def test_get_by_id_returns_none_when_missing(db_session: AsyncSession) -> None:
    repo = SqlAlchemyIncidentRepository(db_session)

    assert await repo.get_by_id(uuid4()) is None


async def test_save_persists_state_history_on_transition(db_session: AsyncSession) -> None:
    incident = _incident()
    repo = SqlAlchemyIncidentRepository(db_session)
    await repo.create(incident)

    occurred_at = datetime(2026, 8, 28, 11, 0, tzinfo=UTC)
    incident.transition_to(IncidentState.INVESTIGATING, occurred_at=occurred_at)
    saved = await repo.save(incident)

    reloaded = await repo.get_by_id(incident.id)
    assert reloaded is not None
    assert saved.state is IncidentState.INVESTIGATING
    assert reloaded.state is IncidentState.INVESTIGATING
    assert len(reloaded.state_history) == 1
    record = reloaded.state_history[0]
    assert record.from_state is IncidentState.OPEN
    assert record.to_state is IncidentState.INVESTIGATING
    assert record.occurred_at == occurred_at


async def test_save_unknown_incident_raises_not_found(db_session: AsyncSession) -> None:
    repo = SqlAlchemyIncidentRepository(db_session)

    with pytest.raises(NotFoundError):
        await repo.save(_incident())


async def test_list_filters_by_state_and_service(db_session: AsyncSession) -> None:
    repo = SqlAlchemyIncidentRepository(db_session)
    payments = _incident(title="Payments", affected_service="payments-api")
    search = _incident(title="Search", affected_service="search-api", severity=Severity.LOW)
    await repo.create(payments)
    await repo.create(search)

    payments.transition_to(IncidentState.INVESTIGATING)
    await repo.save(payments)

    investigating = await repo.list(IncidentFilters(state=IncidentState.INVESTIGATING))
    search_only = await repo.list(IncidentFilters(affected_service="search-api"))
    investigating_ids = {item.id for item in investigating}
    search_ids = {item.id for item in search_only}

    assert payments.id in investigating_ids
    assert search.id not in investigating_ids
    assert search.id in search_ids
    assert payments.id not in search_ids


async def test_list_filters_by_created_date(db_session: AsyncSession) -> None:
    repo = SqlAlchemyIncidentRepository(db_session)
    older = _incident(
        title="Older",
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    newer = _incident(
        title="Newer",
        created_at=datetime(2026, 8, 20, tzinfo=UTC),
    )
    await repo.create(older)
    await repo.create(newer)

    cutoff = datetime(2026, 8, 10, tzinfo=UTC)
    recent_ids = {item.id for item in await repo.list(IncidentFilters(created_after=cutoff))}
    early_ids = {item.id for item in await repo.list(IncidentFilters(created_before=cutoff))}

    assert newer.id in recent_ids
    assert older.id not in recent_ids
    assert older.id in early_ids
    assert newer.id not in early_ids


async def test_list_excludes_soft_deleted_rows(db_session: AsyncSession) -> None:
    incident = _incident()
    repo = SqlAlchemyIncidentRepository(db_session)
    await repo.create(incident)

    row = await db_session.get(IncidentModel, incident.id)
    assert row is not None
    row.deleted_at = datetime.now(UTC) + timedelta(seconds=1)
    await db_session.flush()

    assert await repo.get_by_id(incident.id) is None
    listed_ids = {item.id for item in await repo.list(IncidentFilters())}
    assert incident.id not in listed_ids


async def test_get_open_by_fingerprint_ignores_closed_rows(db_session: AsyncSession) -> None:
    key = "v1|payment|latency_spike|2026-09-02T14"
    repo = SqlAlchemyIncidentRepository(db_session)
    open_row = _incident(fingerprint=key)
    await repo.create(open_row)

    found = await repo.get_open_by_fingerprint(key)
    assert found is not None
    assert found.id == open_row.id

    open_row.transition_to(IncidentState.CLOSED)
    await repo.save(open_row)
    assert await repo.get_open_by_fingerprint(key) is None

    replacement = _incident(title="Second outage", fingerprint=key)
    await repo.create(replacement)
    found_again = await repo.get_open_by_fingerprint(key)
    assert found_again is not None
    assert found_again.id == replacement.id
