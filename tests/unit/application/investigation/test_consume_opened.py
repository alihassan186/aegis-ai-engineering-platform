"""ConsumeOpenedIncident idempotency (FR-020)."""

from __future__ import annotations

import pytest

from aegis.application.evidence.record_evidence import RecordEvidence
from aegis.application.investigation.consume_opened import ConsumeOpenedIncident
from aegis.domain.events.envelope import incident_opened_v1
from aegis.domain.evidence import Evidence, EvidenceKind, EvidenceSource
from aegis.domain.incidents.entity import Incident
from aegis.domain.incidents.enums import IncidentState, Severity
from aegis.shared.exceptions import NotFoundError
from tests.unit.application.evidence.fakes import FakeEvidenceRepository
from tests.unit.application.incidents.fakes import FakeIncidentRepository, FakeProcessedEventStore


class _RecordingRunner:
    def __init__(self) -> None:
        self.started: list[dict[str, str]] = []

    def start(
        self,
        *,
        incident_id: str,
        service: str,
        scenario: str,
        correlation_id: str,
    ) -> None:
        self.started.append(
            {
                "incident_id": incident_id,
                "service": service,
                "scenario": scenario,
                "correlation_id": correlation_id,
            }
        )


def _open_incident() -> Incident:
    return Incident.create(
        title="Checkout latency",
        affected_service="payments-api",
        severity=Severity.HIGH,
    )


async def test_consume_twice_transitions_once() -> None:
    repo = FakeIncidentRepository()
    store = FakeProcessedEventStore()
    runner = _RecordingRunner()
    incident = _open_incident()
    await repo.create(incident)
    event = incident_opened_v1(
        incident_id=str(incident.id),
        correlation_id="req-1",
        event_id="evt-1",
    )
    consume = ConsumeOpenedIncident(repo, store, runner=runner)

    first = await consume.execute(event)
    second = await consume.execute(event)

    assert first.transitioned is True
    assert first.state is IncidentState.INVESTIGATING
    assert second.already_processed is True
    assert second.transitioned is False
    stored = repo.items[incident.id]
    assert stored.state is IncidentState.INVESTIGATING
    assert len(stored.state_history) == 1
    assert runner.started == [
        {
            "incident_id": str(incident.id),
            "service": "payments-api",
            "scenario": "unspecified",
            "correlation_id": "req-1",
        }
    ]


async def test_consume_identified_is_noop_ack() -> None:
    repo = FakeIncidentRepository()
    store = FakeProcessedEventStore()
    runner = _RecordingRunner()
    incident = _open_incident()
    incident.transition_to(IncidentState.INVESTIGATING)
    incident.transition_to(IncidentState.IDENTIFIED)
    await repo.create(incident)
    consume = ConsumeOpenedIncident(repo, store, runner=runner)

    result = await consume.execute(
        incident_opened_v1(incident_id=str(incident.id), correlation_id="req-2")
    )

    assert result.transitioned is False
    assert result.state is IncidentState.IDENTIFIED
    assert repo.items[incident.id].state is IncidentState.IDENTIFIED
    assert runner.started == []
    assert len(repo.saved) == 0


async def test_consume_starts_runner_once_with_fingerprint_scenario() -> None:
    repo = FakeIncidentRepository()
    store = FakeProcessedEventStore()
    runner = _RecordingRunner()
    incident = Incident.create(
        title="Checkout latency",
        affected_service="payments-api",
        severity=Severity.HIGH,
        fingerprint="v1|payments-api|latency_spike|2026-09-14T10",
    )
    await repo.create(incident)
    consume = ConsumeOpenedIncident(repo, store, runner=runner)
    event = incident_opened_v1(incident_id=str(incident.id), correlation_id="corr-graph")

    await consume.execute(event)
    await consume.execute(event)

    assert runner.started == [
        {
            "incident_id": str(incident.id),
            "service": "payments-api",
            "scenario": "latency_spike",
            "correlation_id": "corr-graph",
        }
    ]


async def test_consume_persists_evidence_drained_from_runner() -> None:
    repo = FakeIncidentRepository()
    store = FakeProcessedEventStore()
    evidence_repo = FakeEvidenceRepository()
    incident = _open_incident()
    await repo.create(incident)
    minted = Evidence.create(
        incident_id=incident.id,
        source=EvidenceSource.SIMULATOR,
        kind=EvidenceKind.LOG,
        content_ref="simulator:payment:log",
        summary="timeout",
    )

    class _DrainingRunner(_RecordingRunner):
        def drain_recorded_evidence(self) -> list[Evidence]:
            return [minted]

    consume = ConsumeOpenedIncident(
        repo,
        store,
        runner=_DrainingRunner(),
        record_evidence=RecordEvidence(evidence_repo),
    )

    await consume.execute(
        incident_opened_v1(incident_id=str(incident.id), correlation_id="corr-ev")
    )

    assert [item.id for item in evidence_repo.items] == [minted.id]


async def test_unknown_event_type_is_rejected() -> None:
    consume = ConsumeOpenedIncident(FakeIncidentRepository(), FakeProcessedEventStore())
    event = incident_opened_v1(
        incident_id="11111111-1111-1111-1111-111111111111",
        correlation_id="c",
    )
    broken = type(event)(**{**event.as_detail(), "event_type": "unknown.v1"})

    with pytest.raises(ValueError, match="Unsupported event_type"):
        await consume.execute(broken)


async def test_missing_incident_is_not_acked() -> None:
    consume = ConsumeOpenedIncident(FakeIncidentRepository(), FakeProcessedEventStore())
    event = incident_opened_v1(
        incident_id="11111111-1111-1111-1111-111111111111",
        correlation_id="c",
    )
    with pytest.raises(NotFoundError):
        await consume.execute(event)
