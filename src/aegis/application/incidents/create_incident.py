"""Create a new incident in state ``open`` (FR-001, FR-006)."""

from __future__ import annotations

from aegis.application.incidents.dto import CreateIncidentCommand, IncidentDto
from aegis.core.protocols import IncidentRepository
from aegis.domain.incidents.entity import Incident


class CreateIncident:
    def __init__(self, repository: IncidentRepository) -> None:
        self._repository = repository

    async def execute(self, command: CreateIncidentCommand) -> IncidentDto:
        incident = Incident.create(
            title=command.title,
            affected_service=command.affected_service,
            severity=command.severity,
            description=command.description,
            owner_id=command.owner_id,
        )
        persisted = await self._repository.create(incident)
        print(f"persisted in create_incident.py: {persisted}")
        return IncidentDto.from_entity(persisted)
