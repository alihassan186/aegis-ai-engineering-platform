"""IngestIncidentSignal lookup-or-create (FR-007, FR-113)."""

from __future__ import annotations

from datetime import UTC, datetime

from aegis.application.incidents import (
    CreateIncident,
    CreateIncidentCommand,
    IngestIncidentSignal,
    IngestIncidentSignalCommand,
)
from aegis.domain.incidents import IncidentState, Severity
from tests.unit.application.incidents.fakes import FakeIncidentRepository

_NOW = datetime(2026, 9, 2, 14, 30, tzinfo=UTC)


def _command(**overrides: object) -> IngestIncidentSignalCommand:
    body: dict[str, object] = {
        "source": "simulator",
        "service": "payment",
        "title": "Latency spike on payment",
        "severity": Severity.HIGH,
        "summary": "p99 elevated",
        "scenario": "latency_spike",
        "fingerprint": "client-hint-ignored",
    }
    body.update(overrides)
    return IngestIncidentSignalCommand(**body)  # type: ignore[arg-type]


async def test_ingest_creates_open_incident_for_service() -> None:
    repo = FakeIncidentRepository()
    use_case = IngestIncidentSignal(repo, clock=lambda: _NOW)

    result = await use_case.execute(_command())

    assert result.created is True
    assert result.incident.state is IncidentState.OPEN
    assert result.incident.affected_service == "payment"
    assert result.incident.title == "Latency spike on payment"
    assert result.incident.severity is Severity.HIGH
    assert result.incident.description is not None
    assert "p99 elevated" in result.incident.description
    assert "incident.signal.v1 source=simulator" in result.incident.description
    assert "scenario=latency_spike" in result.incident.description
    assert len(repo.created) == 1
    assert repo.created[0].state is IncidentState.OPEN
    assert repo.created[0].fingerprint == "v1|payment|latency_spike|2026-09-02T14"


async def test_second_ingest_returns_same_id() -> None:
    repo = FakeIncidentRepository()
    use_case = IngestIncidentSignal(repo, clock=lambda: _NOW)

    first = await use_case.execute(_command())
    second = await use_case.execute(_command(title="ignored on duplicate"))

    assert first.created is True
    assert second.created is False
    assert first.incident.id == second.incident.id
    assert len(repo.created) == 1
    assert len(repo.saved) == 1
    assert second.incident.description is not None
    assert "duplicate signal at" in second.incident.description


async def test_distinct_service_creates_a_new_incident() -> None:
    repo = FakeIncidentRepository()
    use_case = IngestIncidentSignal(repo, clock=lambda: _NOW)

    payment = await use_case.execute(_command())
    order = await use_case.execute(
        _command(service="order", scenario="dependency_failure", title="Timeouts on order"),
    )

    assert payment.incident.id != order.incident.id
    assert len(repo.created) == 2


async def test_closed_incident_does_not_dedup() -> None:
    repo = FakeIncidentRepository()
    use_case = IngestIncidentSignal(repo, clock=lambda: _NOW)
    created = await use_case.execute(_command())
    stored = repo.items[created.incident.id]
    stored.transition_to(IncidentState.CLOSED)
    await repo.save(stored)

    again = await use_case.execute(_command())

    assert again.created is True
    assert again.incident.id != created.incident.id
    assert len(repo.created) == 2


async def test_client_fingerprint_hint_does_not_override_computed_key() -> None:
    repo = FakeIncidentRepository()
    use_case = IngestIncidentSignal(repo, clock=lambda: _NOW)

    first = await use_case.execute(_command(fingerprint="hint-a"))
    second = await use_case.execute(_command(fingerprint="hint-b"))

    assert first.incident.id == second.incident.id


async def test_manual_create_without_fingerprint_is_not_collapsed() -> None:
    repo = FakeIncidentRepository()
    create = CreateIncident(repo)

    first = await create.execute(
        CreateIncidentCommand(
            title="Checkout latency",
            affected_service="payment",
            severity=Severity.HIGH,
        )
    )
    ingest = IngestIncidentSignal(repo, clock=lambda: _NOW)
    webhook = await ingest.execute(_command())

    assert first.id != webhook.incident.id
    assert repo.items[first.id].fingerprint is None
