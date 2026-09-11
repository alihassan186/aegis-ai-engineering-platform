"""Repository and service ports.

Concrete implementations belong in ``aegis.infrastructure`` (Step 1.6).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from aegis.core.events import DomainEvent
from aegis.domain.incidents.entity import Incident
from aegis.domain.incidents.enums import IncidentState, Severity


@runtime_checkable
class Embedder(Protocol):
    """Turns texts into dense vectors (FR-040). Implementations live in infrastructure.

    Dimension is Titan Text Embeddings V2 size **1024**. No boto3 in this module.
    """

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True, slots=True)
class KnowledgeHit:
    """One search hit without the embedding vector (FR-044 citations later)."""

    chunk_id: str
    text: str
    source_path: str
    section: str
    score: float


@runtime_checkable
class KnowledgeStore(Protocol):
    """Hybrid knowledge index (FR-043). Implementations live in infrastructure.

    No opensearchpy in this module. Application ingest/retrieve take this port.
    """

    def ensure_hybrid_index(self) -> None: ...

    def bulk_upsert(self, documents: Sequence[Mapping[str, Any]]) -> int: ...

    def count(self) -> int: ...

    def delete_by_source_path(self, source_path: str) -> int: ...

    def search_match(
        self,
        *,
        text: str,
        source_path: str | None = None,
        size: int = 5,
    ) -> list[dict[str, Any]]: ...

    def search_text(
        self,
        *,
        query: str,
        filters: Mapping[str, str],
        size: int,
    ) -> list[KnowledgeHit]: ...

    def search_knn(
        self,
        *,
        embedding: Sequence[float],
        filters: Mapping[str, str],
        size: int,
    ) -> list[KnowledgeHit]: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Publishes versioned domain events (ADR-003). Implementations live in infrastructure.

    No boto3 in this module. Application (Step 4.2 webhook) will take this port.
    """

    def publish(self, event: DomainEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class IncidentFilters:
    """Query options for listing incidents (FR-009)."""

    state: IncidentState | None = None
    severity: Severity | None = None
    affected_service: str | None = None
    owner_id: UUID | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


class IncidentRepository(Protocol):
    """Persistence port for incident aggregates."""

    async def create(self, incident: Incident) -> Incident: ...

    async def get_by_id(self, id: UUID) -> Incident | None: ...

    async def list(self, filters: IncidentFilters) -> list[Incident]: ...

    async def save(self, incident: Incident) -> Incident: ...

    async def get_open_by_fingerprint(self, fingerprint: str) -> Incident | None: ...
