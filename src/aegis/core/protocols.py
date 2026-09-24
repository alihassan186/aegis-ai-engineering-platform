"""Repository and service ports.

Concrete implementations belong in ``aegis.infrastructure`` (Step 1.6).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from aegis.domain.events.envelope import DomainEvent
from aegis.domain.evidence.entity import Evidence
from aegis.domain.incidents.entity import Incident
from aegis.domain.incidents.enums import IncidentState, Severity
from aegis.domain.investigation.progress import InvestigationProgress
from aegis.domain.notifications.entity import Notification
from aegis.domain.rca.entity import RcaReport


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
class NotificationMessage:
    """Outbound notify payload. No evidence dumps, no secrets (FR-027, FR-028)."""

    incident_id: str
    kind: str
    event_type: str
    severity: str
    service: str
    reason: str
    link: str
    rca_version: int | None = None


@runtime_checkable
class Notifier(Protocol):
    """Delivers a notification. Log in CI; SQS/email later. No SMTP here."""

    def notify(self, message: NotificationMessage) -> None: ...


class NotificationRepository(Protocol):
    """Inbox for notify dedupe. ``record_once`` is True only on first insert."""

    async def record_once(self, notification: Notification) -> bool: ...

    async def list_by_incident(self, incident_id: UUID) -> list[Notification]: ...


@runtime_checkable
class ProcessedEventStore(Protocol):
    """Inbox for ``incident_id`` + ``event_type`` + ``schema_version`` (ADR-003).

    ``record_once`` is True only for the first insert. Used so two workers
    cannot both start an investigation. No boto3 in this module.
    """

    async def record_once(
        self,
        *,
        incident_id: UUID,
        event_type: str,
        schema_version: str,
        event_id: str,
        correlation_id: str,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class ObservabilitySignal:
    """One log, metric, or trace **summary** (FR-010–012). Not a raw dump."""

    kind: str
    source: str
    timestamp: datetime
    service: str
    summary: str


@runtime_checkable
class ObservabilitySource(Protocol):
    """Read-only telemetry. Implementations live in infrastructure (simulator HTTP)."""

    def fetch_signals(
        self,
        *,
        service: str,
        scenario: str,
        limit: int = 20,
    ) -> Sequence[ObservabilitySignal]: ...


@dataclass(frozen=True, slots=True)
class CodeHit:
    """Deploy version and/or a fake repo path (FR-013, FR-014). Not a ``src/`` walk."""

    service: str
    version: str
    path: str
    summary: str


@runtime_checkable
class CodeSearch(Protocol):
    """Read-only code/deploy search. GitHub through the gateway is Phase 5."""

    def recent_deploys(self, *, service: str) -> Sequence[CodeHit]: ...

    def search(self, *, service: str, scenario: str) -> Sequence[CodeHit]: ...


@runtime_checkable
class InvestigationRunner(Protocol):
    """Starts the investigation graph after ``open`` → ``investigating``.

    Implementations live in application (LangGraph). No LangGraph types here
    so messaging/worker composition stays a port. ``thread_id`` is ``incident_id``.
    """

    def start(
        self,
        *,
        incident_id: str,
        service: str,
        scenario: str,
        correlation_id: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class IncidentFilters:
    """Query options for listing incidents (FR-009)."""

    state: IncidentState | None = None
    severity: Severity | None = None
    affected_service: str | None = None
    owner_id: UUID | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


@dataclass(frozen=True, slots=True)
class LlmJsonResult:
    """Structured model output plus token attribution (NFR-045, NFR-070)."""

    data: Mapping[str, Any]
    model_id: str
    input_tokens: int
    output_tokens: int


@runtime_checkable
class LlmClient(Protocol):
    """JSON completion port. No boto3 here. Fake in CI; Claude via Bedrock."""

    def complete_json(self, *, system: str, user: str) -> LlmJsonResult: ...


class RcaRepository(Protocol):
    """Persistence port for RCA versions (FR-035). HTTP accept is Step 4.9."""

    async def add(self, report: RcaReport) -> RcaReport: ...

    async def save(self, report: RcaReport) -> RcaReport: ...

    async def list_by_incident(self, incident_id: UUID) -> list[RcaReport]: ...


class InvestigationProgressRepository(Protocol):
    """Persisted investigation steps and pause flag (FR-022, FR-023)."""

    async def get_by_incident(self, incident_id: UUID) -> InvestigationProgress | None: ...

    async def save(self, progress: InvestigationProgress) -> InvestigationProgress: ...


class EvidenceRepository(Protocol):
    """Persistence port for incident-scoped evidence (FR-018). No embeddings."""

    async def add(self, evidence: Evidence) -> Evidence: ...

    async def list_by_incident(self, incident_id: UUID) -> list[Evidence]: ...


class IncidentRepository(Protocol):
    """Persistence port for incident aggregates."""

    async def create(self, incident: Incident) -> Incident: ...

    async def get_by_id(self, id: UUID) -> Incident | None: ...

    async def list(self, filters: IncidentFilters) -> list[Incident]: ...

    async def save(self, incident: Incident) -> Incident: ...

    async def get_open_by_fingerprint(self, fingerprint: str) -> Incident | None: ...
