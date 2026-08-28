"""Advance an incident through the domain state machine (FR-003, FR-004)."""

from __future__ import annotations

from aegis.application.incidents.dto import IncidentDto, TransitionIncidentCommand
from aegis.core.protocols import IncidentRepository
from aegis.shared.exceptions import NotFoundError


class TransitionIncident:
    def __init__(self, repository: IncidentRepository) -> None:
        self._repository = repository

    async def execute(self, command: TransitionIncidentCommand) -> IncidentDto:
        incident = await self._repository.get_by_id(command.incident_id)
        if incident is None:
            raise NotFoundError(f"Incident '{command.incident_id}' was not found.")
        incident.transition_to(command.new_state)
        persisted = await self._repository.save(incident)
        return IncidentDto.from_entity(persisted)
