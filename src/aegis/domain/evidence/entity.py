"""Evidence child entity — incident-scoped, durable, citeable (FR-017, FR-018).

Incident remains the aggregate root for lifecycle. Evidence is a child
collection scoped by ``incident_id`` (THR-012). RCA in 4.8 cites ``id``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from aegis.domain.evidence.enums import EvidenceKind, EvidenceSource
from aegis.shared.exceptions import ValidationError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(moment: datetime, field_name: str) -> datetime:
    if moment.tzinfo is None:
        raise ValidationError(f"{field_name} must be timezone-aware.")
    return moment


def _require_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(f"{field_name} must not be empty.")
    return cleaned


def _sanitize_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Copy metadata. Never persist embeddings (those belong in OpenSearch)."""
    raw = dict(metadata or {})
    raw.pop("embedding", None)
    raw.pop("embeddings", None)
    return raw


class Evidence:
    """Immutable evidence row. Mutate by creating a new instance."""

    def __init__(
        self,
        *,
        id: UUID,
        incident_id: UUID,
        source: EvidenceSource,
        kind: EvidenceKind,
        content_ref: str,
        summary: str,
        metadata: Mapping[str, Any],
        collected_at: datetime,
    ) -> None:
        self._id = id
        self._incident_id = incident_id
        self._source = source
        self._kind = kind
        self._content_ref = _require_text(content_ref, "content_ref")
        self._summary = summary.strip()
        self._metadata = _sanitize_metadata(metadata)
        self._collected_at = _require_aware(collected_at, "collected_at")
        if not self._summary and not self._content_ref:
            raise ValidationError("evidence requires a content_ref or summary.")

    @classmethod
    def create(
        cls,
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
        if incident_id is None:
            raise ValidationError("incident_id is required.")
        return cls(
            id=evidence_id or uuid4(),
            incident_id=incident_id,
            source=source,
            kind=kind,
            content_ref=content_ref,
            summary=summary,
            metadata=metadata or {},
            collected_at=collected_at or _utc_now(),
        )

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def incident_id(self) -> UUID:
        return self._incident_id

    @property
    def source(self) -> EvidenceSource:
        return self._source

    @property
    def kind(self) -> EvidenceKind:
        return self._kind

    @property
    def content_ref(self) -> str:
        return self._content_ref

    @property
    def summary(self) -> str:
        return self._summary

    @property
    def metadata(self) -> Mapping[str, Any]:
        return dict(self._metadata)

    @property
    def collected_at(self) -> datetime:
        return self._collected_at
