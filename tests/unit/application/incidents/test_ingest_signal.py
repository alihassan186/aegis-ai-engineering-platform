"""IngestIncidentSignal maps onto CreateIncident (FR-113)."""

from __future__ import annotations

from aegis.application.incidents import (
    CreateIncident,
    IngestIncidentSignal,
    IngestIncidentSignalCommand,
)
from aegis.domain.incidents import IncidentState, Severity
from tests.unit.application.incidents.fakes import FakeIncidentRepository


async def test_ingest_creates_open_incident_for_service() -> None:
    repo = FakeIncidentRepository()
    use_case = IngestIncidentSignal(CreateIncident(repo))

    result = await use_case.execute(
        IngestIncidentSignalCommand(
            source="simulator",
            service="payment",
            title="Latency spike on payment",
            severity=Severity.HIGH,
            summary="p99 elevated",
            scenario="latency_spike",
            fingerprint="payment:latency_spike",
        )
    )

    assert result.state is IncidentState.OPEN
    assert result.affected_service == "payment"
    assert result.title == "Latency spike on payment"
    assert result.severity is Severity.HIGH
    assert result.description is not None
    assert "p99 elevated" in result.description
    assert "incident.signal.v1 source=simulator" in result.description
    assert "scenario=latency_spike" in result.description
    assert len(repo.created) == 1
    assert repo.created[0].state is IncidentState.OPEN
