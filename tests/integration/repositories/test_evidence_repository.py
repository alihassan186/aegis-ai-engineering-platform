"""Evidence rows survive in Postgres (unlike InMemorySaver graph state)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from aegis.application.evidence.record_evidence import RecordEvidence
from aegis.application.investigation.runner import LangGraphInvestigationRunner
from aegis.domain.evidence import Evidence, EvidenceKind, EvidenceSource
from aegis.domain.incidents import Incident, Severity
from aegis.infrastructure.repositories.evidence_repository import SqlAlchemyEvidenceRepository
from aegis.infrastructure.repositories.incident_repository import SqlAlchemyIncidentRepository


def _incident() -> Incident:
    return Incident.create(
        title="Checkout latency",
        affected_service="payments-api",
        severity=Severity.HIGH,
    )


async def test_add_and_list_by_incident(db_session: AsyncSession) -> None:
    incidents = SqlAlchemyIncidentRepository(db_session)
    first = await incidents.create(_incident())
    second = await incidents.create(
        Incident.create(
            title="Other",
            affected_service="user-api",
            severity=Severity.LOW,
        )
    )
    repo = SqlAlchemyEvidenceRepository(db_session)
    use_case = RecordEvidence(repo)

    older = await use_case.execute(
        incident_id=first.id,
        source=EvidenceSource.SIMULATOR,
        kind=EvidenceKind.LOG,
        content_ref="simulator:payment:log:1",
        summary="checkout timeout",
        metadata={"tool": "observability"},
        collected_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
    )
    newer = await use_case.execute(
        incident_id=first.id,
        source=EvidenceSource.RETRIEVE,
        kind=EvidenceKind.CHUNK,
        content_ref="chunk-latency",
        summary="restart checkout workers",
        metadata={"tool": "retrieve", "query": "latency spike"},
        collected_at=datetime(2026, 9, 20, 12, 1, tzinfo=UTC),
    )
    await use_case.execute(
        incident_id=second.id,
        source=EvidenceSource.MANUAL,
        kind=EvidenceKind.NOTE,
        content_ref="manual",
        summary="belongs to the other incident",
    )

    listed = await repo.list_by_incident(first.id)

    assert [item.id for item in listed] == [older.id, newer.id]
    assert listed[0].source is EvidenceSource.SIMULATOR
    assert listed[1].kind is EvidenceKind.CHUNK
    assert "embedding" not in listed[1].metadata
    assert listed[1].metadata["query"] == "latency spike"


async def test_graph_collect_path_writes_at_least_one_row(db_session: AsyncSession) -> None:
    incident = await SqlAlchemyIncidentRepository(db_session).create(_incident())
    runner = LangGraphInvestigationRunner()
    runner.start(
        incident_id=str(incident.id),
        service="payment",
        scenario="latency_spike",
        correlation_id="int-4-6",
    )

    use_case = RecordEvidence(SqlAlchemyEvidenceRepository(db_session))
    minted = runner.drain_recorded_evidence()
    assert minted
    for item in minted:
        await use_case.persist(item)

    listed = await use_case.list_for_incident(incident.id)
    assert len(listed) >= 1
    assert all(item.incident_id == incident.id for item in listed)
    assert all(isinstance(item, Evidence) for item in listed)
    assert {item.source for item in listed} <= set(EvidenceSource)


async def test_list_empty_when_incident_has_no_evidence(db_session: AsyncSession) -> None:
    repo = SqlAlchemyEvidenceRepository(db_session)
    assert await repo.list_by_incident(uuid4()) == []
