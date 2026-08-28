"""In-memory IncidentRepository for application unit tests."""

from __future__ import annotations

from uuid import UUID

from aegis.core.protocols import IncidentFilters
from aegis.domain.incidents.entity import Incident
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
