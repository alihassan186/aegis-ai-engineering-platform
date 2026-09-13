"""Create a new incident in state ``open`` (FR-001, FR-006, FR-020).

Publish choice (Step 4.2): the use case calls ``EventPublisher`` *after*
the row is flushed. HTTP composition buffers that call and flushes only
**after** the request session commits (NFR-011). If EventBridge then
fails we log and still return 201 — a full transactional outbox is
deferred (dual-write can lose the event if the bus is down).
"""

from __future__ import annotations

from aegis.application.incidents.dto import CreateIncidentCommand, IncidentDto
from aegis.core.protocols import EventPublisher, IncidentRepository
from aegis.domain.events.envelope import incident_opened_v1
from aegis.domain.incidents.entity import Incident


class CreateIncident:
    def __init__(
        self,
        repository: IncidentRepository,
        publisher: EventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._publisher = publisher

    async def execute(
        self,
        command: CreateIncidentCommand,
        *,
        correlation_id: str = "unknown",
    ) -> IncidentDto:
        incident = Incident.create(
            title=command.title,
            affected_service=command.affected_service,
            severity=command.severity,
            description=command.description,
            owner_id=command.owner_id,
            fingerprint=command.fingerprint,
        )
        persisted = await self._repository.create(incident)
        if self._publisher is not None:
            self._publisher.publish(
                incident_opened_v1(
                    incident_id=str(persisted.id),
                    correlation_id=correlation_id,
                )
            )
        return IncidentDto.from_entity(persisted)
