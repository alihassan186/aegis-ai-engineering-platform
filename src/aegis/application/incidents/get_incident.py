"""Load one incident by id (FR-002)."""

from __future__ import annotations

from uuid import UUID

from aegis.application.incidents.dto import IncidentDto
from aegis.core.protocols import IncidentRepository
from aegis.shared.exceptions import NotFoundError


class GetIncident:
    def __init__(self, repository: IncidentRepository) -> None:
        self._repository = repository

    async def execute(self, incident_id: UUID) -> IncidentDto:
        incident = await self._repository.get_by_id(incident_id)
        if incident is None:
            raise NotFoundError(f"Incident '{incident_id}' was not found.")
        return IncidentDto.from_entity(incident)
