"""Record evidence against an incident (FR-017, FR-018, FR-019).

Graph nodes call this use case's **mapping + recorder**, not a SQLAlchemy
session. The worker persists via ``EvidenceRepository`` after collect.
Every write goes through ``redact`` so a specialist cannot persist a token.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from aegis.application.security.redact import (
    marker_count,
    redact,
    redact_for_llm,
    redact_mapping,
)
from aegis.core.protocols import EvidenceRepository
from aegis.domain.evidence.entity import Evidence
from aegis.domain.evidence.enums import EvidenceKind, EvidenceSource
from aegis.shared.exceptions import ValidationError

# Keep in lockstep with investigation.state.EVIDENCE_TEXT_CAP (avoid a circular import).
EVIDENCE_TEXT_CAP = 800


def apply_redaction(text: str) -> str:
    """Redact secrets. Same helper the 4.8 prompt assembler will call."""
    return redact_for_llm(text)


def _cap(text: str) -> str:
    stripped = redact(text.strip()).text
    if len(stripped) <= EVIDENCE_TEXT_CAP:
        return stripped
    return stripped[: EVIDENCE_TEXT_CAP - 3] + "..."


def prepare_evidence(evidence: Evidence) -> Evidence:
    """Redact summary, pointer, and metadata strings before any repository add."""
    summary = redact(evidence.summary)
    content_ref = redact(evidence.content_ref)
    metadata, meta_hits = redact_mapping(dict(evidence.metadata))
    if not isinstance(metadata, dict):
        metadata = {}
    hits = summary.count + content_ref.count + meta_hits
    existing = metadata.get("redaction_count")
    prior = existing if isinstance(existing, int) else 0
    markers = marker_count(summary.text, content_ref.text) + _metadata_markers(metadata)
    metadata["redaction_count"] = max(hits, prior, markers)
    return Evidence(
        id=evidence.id,
        incident_id=evidence.incident_id,
        source=evidence.source,
        kind=evidence.kind,
        content_ref=content_ref.text,
        summary=summary.text,
        metadata=metadata,
        collected_at=evidence.collected_at,
    )


def _metadata_markers(metadata: Mapping[str, Any]) -> int:
    total = 0
    for value in metadata.values():
        if isinstance(value, str):
            total += marker_count(value)
        elif isinstance(value, Mapping):
            total += _metadata_markers(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    total += marker_count(item)
                elif isinstance(item, Mapping):
                    total += _metadata_markers(item)
    return total


def _parse_collected_at(raw: object) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evidence_from_collected_item(incident_id: UUID, item: Mapping[str, Any]) -> Evidence:
    """Map a 4.5 graph item onto a domain evidence row (UUID minted now)."""
    collector = str(item.get("collector") or "").strip().lower()
    if collector == "observability":
        kind_raw = str(item.get("kind") or "log")
        try:
            kind = EvidenceKind(kind_raw)
        except ValueError:
            kind = EvidenceKind.LOG
        service = str(item.get("service") or "")
        stamp = str(item.get("timestamp") or "")
        return prepare_evidence(
            Evidence.create(
                incident_id=incident_id,
                source=EvidenceSource.SIMULATOR,
                kind=kind,
                content_ref=f"simulator:{service}:{kind.value}:{stamp}",
                summary=_cap(str(item.get("summary") or "")),
                metadata={"tool": "observability", "service": service},
                collected_at=_parse_collected_at(item.get("timestamp")),
            )
        )
    if collector == "knowledge":
        citation = item.get("citation") if isinstance(item.get("citation"), Mapping) else {}
        chunk_id = str(citation.get("chunk_id") or citation.get("document") or "retrieve")
        return prepare_evidence(
            Evidence.create(
                incident_id=incident_id,
                source=EvidenceSource.RETRIEVE,
                kind=EvidenceKind.CHUNK,
                content_ref=chunk_id,
                summary=_cap(str(item.get("text") or "")),
                metadata={
                    "tool": "retrieve",
                    "citation": dict(citation),
                    "query": item.get("query"),
                },
                collected_at=_parse_collected_at(item.get("timestamp")),
            )
        )
    if collector == "code":
        path = str(item.get("path") or f"code:{item.get('service') or 'unknown'}")
        kind = EvidenceKind.DEPLOY if item.get("kind") == "deploy" else EvidenceKind.NOTE
        return prepare_evidence(
            Evidence.create(
                incident_id=incident_id,
                source=EvidenceSource.CODE,
                kind=kind,
                content_ref=path,
                summary=_cap(str(item.get("summary") or "")),
                metadata={
                    "tool": "code_search",
                    "version": item.get("version"),
                    "path": path,
                    "service": item.get("service"),
                },
                collected_at=_parse_collected_at(item.get("timestamp")),
            )
        )
    return prepare_evidence(
        Evidence.create(
            incident_id=incident_id,
            source=EvidenceSource.MANUAL,
            kind=EvidenceKind.NOTE,
            content_ref=str(item.get("content_ref") or "manual"),
            summary=_cap(str(item.get("summary") or item.get("text") or "")),
            metadata={"tool": "manual", **{k: v for k, v in item.items() if k != "embedding"}},
            collected_at=_parse_collected_at(item.get("timestamp") or item.get("collected_at")),
        )
    )


class EvidenceRecorder(Protocol):
    """Sync sink used by graph nodes (no session, no await)."""

    def record_collected(
        self,
        incident_id: UUID,
        items: Sequence[Mapping[str, Any]],
    ) -> list[Evidence]: ...


class CollectingEvidenceRecorder:
    """Holds minted evidence until the worker use case persists them."""

    def __init__(self, bucket: list[Evidence] | None = None) -> None:
        self.recorded: list[Evidence] = bucket if bucket is not None else []

    def record_collected(
        self,
        incident_id: UUID,
        items: Sequence[Mapping[str, Any]],
    ) -> list[Evidence]:
        created = [evidence_from_collected_item(incident_id, item) for item in items]
        self.recorded.extend(created)
        return created


class RecordEvidence:
    """Application use case: validate + store. Infrastructure owns SQL."""

    def __init__(self, repository: EvidenceRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        incident_id: UUID,
        source: EvidenceSource,
        kind: EvidenceKind,
        content_ref: str,
        summary: str = "",
        metadata: Mapping[str, Any] | None = None,
        collected_at: datetime | None = None,
        evidence_id: UUID | None = None,
    ) -> Evidence:
        evidence = prepare_evidence(
            Evidence.create(
                incident_id=incident_id,
                source=source,
                kind=kind,
                content_ref=content_ref,
                summary=summary,
                metadata=metadata,
                collected_at=collected_at,
                evidence_id=evidence_id,
            )
        )
        return await self._repository.add(evidence)

    async def persist(self, evidence: Evidence) -> Evidence:
        return await self._repository.add(prepare_evidence(evidence))

    async def list_for_incident(self, incident_id: UUID) -> list[Evidence]:
        return await self._repository.list_by_incident(incident_id)


def incident_id_from_state(raw: object) -> UUID | None:
    """Graph CLI uses ``INC-LEARN-*``; only persist when the id is a UUID."""
    try:
        return UUID(str(raw))
    except (ValueError, TypeError, ValidationError):
        return None
