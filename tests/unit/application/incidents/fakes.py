"""In-memory IncidentRepository for application unit tests."""

from __future__ import annotations

from uuid import UUID

from aegis.core.protocols import IncidentFilters
from aegis.domain.events.envelope import DomainEvent
from aegis.domain.incidents.entity import Incident
from aegis.domain.incidents.enums import IncidentState
from aegis.shared.exceptions import NotFoundError


class FakeIncidentRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Incident] = {}
        self.created: list[Incident] = []
        self.saved: list[Incident] = []
        self.last_filters: IncidentFilters | None = None

    async def create(self, incident: Incident) -> Incident:
        self.items[incident.id] = incident
        self.created.append(incident)
        return incident

    async def get_by_id(self, id: UUID) -> Incident | None:
        return self.items.get(id)

    async def list(self, filters: IncidentFilters) -> list[Incident]:
        self.last_filters = filters
        return list(self.items.values())

    async def save(self, incident: Incident) -> Incident:
        if incident.id not in self.items:
            raise NotFoundError(f"Incident '{incident.id}' was not found.")
        self.items[incident.id] = incident
        self.saved.append(incident)
        return incident

    async def get_open_by_fingerprint(self, fingerprint: str) -> Incident | None:
        for incident in self.items.values():
            if incident.fingerprint == fingerprint and incident.state is IncidentState.OPEN:
                return incident
        return None


class FakeEventPublisher:
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


class FakeProcessedEventStore:
    def __init__(self) -> None:
        self.keys: set[tuple[UUID, str, str]] = set()

    async def record_once(
        self,
        *,
        incident_id: UUID,
        event_type: str,
        schema_version: str,
        event_id: str,
        correlation_id: str,
    ) -> bool:
        key = (incident_id, event_type, schema_version)
        if key in self.keys:
            return False
        self.keys.add(key)
        return True
