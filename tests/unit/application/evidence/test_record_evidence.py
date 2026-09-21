"""RecordEvidence stores two items and lists them by incident id."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from aegis.application.evidence.record_evidence import (
    CollectingEvidenceRecorder,
    RecordEvidence,
    apply_redaction,
    evidence_from_collected_item,
    incident_id_from_state,
)
from aegis.application.investigation.collect import (
    MemoryObservabilitySource,
    collect_observability,
)
from aegis.domain.evidence import Evidence, EvidenceKind, EvidenceSource
from tests.unit.application.evidence.fakes import FakeEvidenceRepository


def _state(incident_id: str) -> dict[str, object]:
    return {
        "incident_id": incident_id,
        "service": "payment",
        "scenario": "latency_spike",
        "hops": 1,
        "next_agent": "",
        "status": "running",
        "human_decision": "",
        "evidence": [],
        "log": [],
        "failed_steps": [],
    }


async def test_two_items_for_one_incident_list_by_id() -> None:
    incident_id = uuid4()
    other_id = uuid4()
    use_case = RecordEvidence(FakeEvidenceRepository())

    first = await use_case.execute(
        incident_id=incident_id,
        source=EvidenceSource.SIMULATOR,
        kind=EvidenceKind.LOG,
        content_ref="simulator:payment:log:1",
        summary="timeout in checkout",
        collected_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
    )
    second = await use_case.execute(
        incident_id=incident_id,
        source=EvidenceSource.RETRIEVE,
        kind=EvidenceKind.CHUNK,
        content_ref="docs/knowledge/runbooks/payment-latency-spike.md#chunk-0",
        summary="restart checkout workers",
        metadata={"tool": "retrieve", "query": "latency spike"},
        collected_at=datetime(2026, 9, 20, 12, 1, tzinfo=UTC),
    )
    await use_case.execute(
        incident_id=other_id,
        source=EvidenceSource.MANUAL,
        kind=EvidenceKind.NOTE,
        content_ref="manual",
        summary="other incident",
    )

    listed = await use_case.list_for_incident(incident_id)

    assert [item.id for item in listed] == [first.id, second.id]
    assert all(item.incident_id == incident_id for item in listed)
    assert listed[0].source is EvidenceSource.SIMULATOR
    assert listed[1].kind is EvidenceKind.CHUNK


async def test_persist_round_trips_minted_uuid() -> None:
    repo = FakeEvidenceRepository()
    use_case = RecordEvidence(repo)
    minted = Evidence.create(
        incident_id=uuid4(),
        source=EvidenceSource.CODE,
        kind=EvidenceKind.DEPLOY,
        content_ref="docs/knowledge/services/user.md",
        summary="user 1.14.0",
    )

    stored = await use_case.persist(minted)

    assert stored.id == minted.id
    assert repo.items[0].id == minted.id


def test_graph_item_maps_to_simulator_log() -> None:
    incident_id = uuid4()
    evidence = evidence_from_collected_item(
        incident_id,
        {
            "collector": "observability",
            "kind": "log",
            "service": "payment",
            "timestamp": "2026-09-20T12:00:00Z",
            "summary": "p99 1.8s",
        },
    )

    assert evidence.incident_id == incident_id
    assert evidence.source is EvidenceSource.SIMULATOR
    assert evidence.kind is EvidenceKind.LOG
    assert "p99 1.8s" in evidence.summary
    assert evidence.metadata["tool"] == "observability"


def test_knowledge_item_maps_citation_without_embedding() -> None:
    evidence = evidence_from_collected_item(
        uuid4(),
        {
            "collector": "knowledge",
            "text": "scale the pool",
            "query": "db exhaustion",
            "citation": {
                "document": "docs/knowledge/runbooks/payment-db-exhaustion.md",
                "chunk_id": "chunk-9",
            },
            "embedding": [0.1],
        },
    )

    assert evidence.source is EvidenceSource.RETRIEVE
    assert evidence.kind is EvidenceKind.CHUNK
    assert evidence.content_ref == "chunk-9"
    assert "embedding" not in evidence.metadata
    assert evidence.metadata["citation"]["chunk_id"] == "chunk-9"


def test_code_deploy_and_manual_sources() -> None:
    deploy = evidence_from_collected_item(
        uuid4(),
        {
            "collector": "code",
            "kind": "deploy",
            "path": "docs/knowledge/services/user.md",
            "summary": "user 1.14.0",
            "version": "1.14.0",
        },
    )
    note = evidence_from_collected_item(
        uuid4(),
        {"content_ref": "pager", "summary": "on-call note", "collected_at": "2026-09-20T13:00:00Z"},
    )

    assert deploy.source is EvidenceSource.CODE
    assert deploy.kind is EvidenceKind.DEPLOY
    assert note.source is EvidenceSource.MANUAL
    assert note.kind is EvidenceKind.NOTE


def test_redaction_strips_dummy_aws_key() -> None:
    assert "AKIAIOSFODNN7EXAMPLE" not in apply_redaction("key=AKIAIOSFODNN7EXAMPLE")
    assert "[REDACTED:aws_access_key]" in apply_redaction("key=AKIAIOSFODNN7EXAMPLE")


async def test_record_evidence_persists_redacted_body() -> None:
    repo = FakeEvidenceRepository()
    use_case = RecordEvidence(repo)
    dummy = "AKIAIOSFODNN7EXAMPLE"

    stored = await use_case.execute(
        incident_id=uuid4(),
        source=EvidenceSource.SIMULATOR,
        kind=EvidenceKind.LOG,
        content_ref="simulator:payment:log:1",
        summary=f"checkout auth failed key={dummy}",
        metadata={"query": "postgresql+asyncpg://dummy:dummy-pass-NOT-REAL@127.0.0.1:5434/aegis"},
    )

    assert dummy not in stored.summary
    assert "dummy-pass-NOT-REAL" not in stored.summary
    assert "dummy-pass-NOT-REAL" not in str(stored.metadata)
    assert "[REDACTED:aws_access_key]" in stored.summary
    assert stored.metadata["redaction_count"] >= 2
    assert dummy not in repo.items[0].summary


async def test_persist_redacts_even_if_entity_was_built_raw() -> None:
    repo = FakeEvidenceRepository()
    dummy = "ghp_dummyNotARealGitHubPatToken"
    minted = Evidence.create(
        incident_id=uuid4(),
        source=EvidenceSource.RETRIEVE,
        kind=EvidenceKind.CHUNK,
        content_ref="chunk-1",
        summary=f"runbook mentions {dummy}",
    )

    stored = await RecordEvidence(repo).persist(minted)

    assert dummy not in stored.summary
    assert dummy not in repo.items[0].summary
    assert "[REDACTED:github_pat]" in stored.summary


def test_collected_knowledge_excerpt_is_redacted() -> None:
    dummy_jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiJkdW1teS11c2VyIn0."
        "dummy_signature_not_a_real_secret"
    )
    evidence = evidence_from_collected_item(
        uuid4(),
        {
            "collector": "knowledge",
            "text": f"do not replay {dummy_jwt}",
            "citation": {"chunk_id": "chunk-9", "document": "docs/knowledge/runbooks/x.md"},
        },
    )

    assert dummy_jwt not in evidence.summary
    assert "[REDACTED:jwt]" in evidence.summary
    assert evidence.metadata["redaction_count"] >= 1


def test_cli_incident_ids_are_not_persisted() -> None:
    assert incident_id_from_state("INC-LEARN-abcd") is None
    assert incident_id_from_state("INC-TEST") is None
    assert incident_id_from_state(uuid4()) is not None


def test_specialist_records_after_successful_collect() -> None:
    incident_id = uuid4()
    recorder = CollectingEvidenceRecorder()

    update = collect_observability(
        _state(str(incident_id)),  # type: ignore[arg-type]
        MemoryObservabilitySource(),
        recorder=recorder,
    )

    assert update["evidence"]
    assert len(recorder.recorded) == len(update["evidence"])
    assert recorder.recorded[0].incident_id == incident_id
    assert recorder.recorded[0].source is EvidenceSource.SIMULATOR
