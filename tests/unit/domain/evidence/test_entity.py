"""Evidence requires incident_id, source, and timezone-aware collected_at."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from aegis.domain.evidence import Evidence, EvidenceKind, EvidenceSource
from aegis.shared.exceptions import ValidationError


def test_create_requires_incident_id_source_and_collected_at() -> None:
    incident_id = uuid4()
    collected_at = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)

    evidence = Evidence.create(
        incident_id=incident_id,
        source=EvidenceSource.SIMULATOR,
        kind=EvidenceKind.LOG,
        content_ref="simulator:payment:log:2026-09-20T12:00:00+00:00",
        summary="p99 latency 1.8s",
        collected_at=collected_at,
    )

    assert isinstance(evidence.id, UUID)
    assert evidence.incident_id == incident_id
    assert evidence.source is EvidenceSource.SIMULATOR
    assert evidence.kind is EvidenceKind.LOG
    assert evidence.collected_at == collected_at
    assert evidence.summary == "p99 latency 1.8s"


def test_create_rejects_missing_incident_id() -> None:
    with pytest.raises(ValidationError, match="incident_id"):
        Evidence.create(
            incident_id=None,  # type: ignore[arg-type]
            source=EvidenceSource.SIMULATOR,
            kind=EvidenceKind.LOG,
            content_ref="simulator:payment:log",
        )


def test_create_rejects_naive_collected_at() -> None:
    with pytest.raises(ValidationError, match="collected_at"):
        Evidence.create(
            incident_id=uuid4(),
            source=EvidenceSource.SIMULATOR,
            kind=EvidenceKind.METRIC,
            content_ref="simulator:payment:metric",
            collected_at=datetime(2026, 9, 20, 12, 0),
        )


def test_create_rejects_blank_content_ref() -> None:
    with pytest.raises(ValidationError, match="content_ref"):
        Evidence.create(
            incident_id=uuid4(),
            source=EvidenceSource.MANUAL,
            kind=EvidenceKind.NOTE,
            content_ref="   ",
        )


def test_manual_source_is_allowed_before_api_exists() -> None:
    evidence = Evidence.create(
        incident_id=uuid4(),
        source=EvidenceSource.MANUAL,
        kind=EvidenceKind.NOTE,
        content_ref="operator-note",
        summary="on-call confirmed checkout timeouts",
    )

    assert evidence.source is EvidenceSource.MANUAL
    assert isinstance(evidence.id, UUID)


def test_create_strips_embeddings_from_metadata() -> None:
    evidence = Evidence.create(
        incident_id=uuid4(),
        source=EvidenceSource.RETRIEVE,
        kind=EvidenceKind.CHUNK,
        content_ref="chunk-1",
        metadata={
            "citation": {"chunk_id": "chunk-1"},
            "embedding": [0.1, 0.2],
            "embeddings": [[0.3]],
            "query": "latency spike",
        },
    )

    assert "embedding" not in evidence.metadata
    assert "embeddings" not in evidence.metadata
    assert evidence.metadata["query"] == "latency spike"


def test_create_mints_distinct_ids() -> None:
    incident_id = uuid4()
    first = Evidence.create(
        incident_id=incident_id,
        source=EvidenceSource.CODE,
        kind=EvidenceKind.DEPLOY,
        content_ref="docs/knowledge/services/user.md",
    )
    second = Evidence.create(
        incident_id=incident_id,
        source=EvidenceSource.CODE,
        kind=EvidenceKind.DEPLOY,
        content_ref="docs/knowledge/services/user.md",
    )

    assert first.id != second.id
