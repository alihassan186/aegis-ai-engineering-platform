"""List incidents with FR-009 filters."""

from __future__ import annotations

from aegis.application.incidents.dto import IncidentDto, ListIncidentsQuery
from aegis.core.protocols import IncidentFilters, IncidentRepository


class ListIncidents:
    def __init__(self, repository: IncidentRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListIncidentsQuery) -> list[IncidentDto]:
        filters = IncidentFilters(
            state=query.state,
            severity=query.severity,
            affected_service=query.affected_service,
            owner_id=query.owner_id,
            created_after=query.created_after,
            created_before=query.created_before,
        )
        incidents = await self._repository.list(filters)
        return [IncidentDto.from_entity(incident) for incident in incidents]
