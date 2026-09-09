"""Repository and service ports.

Concrete implementations belong in ``aegis.infrastructure`` (Step 1.6).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from aegis.domain.incidents.entity import Incident
from aegis.domain.incidents.enums import IncidentState, Severity


@runtime_checkable
class Embedder(Protocol):
    """Turns texts into dense vectors (FR-040). Implementations live in infrastructure.

    Dimension is Titan Text Embeddings V2 size **1024**. No boto3 in this module.
    """

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class KnowledgeStore(Protocol):
    """Hybrid knowledge index (FR-043). Implementations live in infrastructure.

    No opensearchpy in this module. Application ingest takes this port, not a client.
    """

    def ensure_hybrid_index(self) -> None: ...

    def bulk_upsert(self, documents: Sequence[Mapping[str, Any]]) -> int: ...

    def count(self) -> int: ...

    def search_match(
        self,
        *,
        text: str,
        source_path: str | None = None,
        size: int = 5,
    ) -> list[dict[str, Any]]: ...


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
