"""Ingest an incident.signal.v1 webhook: lookup-or-create (FR-007, FR-113)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from aegis.application.incidents.create_incident import CreateIncident
from aegis.application.incidents.dto import (
    CreateIncidentCommand,
    IncidentDto,
    IngestIncidentSignalCommand,
    IngestIncidentSignalResult,
)
from aegis.core.protocols import IncidentRepository
from aegis.domain.incidents.fingerprint import compute_fingerprint

Clock = Callable[[], datetime]


class IngestIncidentSignal:
    def __init__(
        self,
        repository: IncidentRepository,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._repository = repository
        self._create = CreateIncident(repository)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def execute(self, command: IngestIncidentSignalCommand) -> IngestIncidentSignalResult:
        occurred_at = self._clock()
        fingerprint = compute_fingerprint(
            affected_service=command.service,
            scenario=command.scenario,
            occurred_at=occurred_at,
        )
        existing = await self._repository.get_open_by_fingerprint(fingerprint)
        if existing is not None:
            existing.note_duplicate_signal(occurred_at=occurred_at)
            persisted = await self._repository.save(existing)
            return IngestIncidentSignalResult(
                incident=IncidentDto.from_entity(persisted),
                created=False,
            )

        created = await self._create.execute(
            CreateIncidentCommand(
                title=command.title,
                affected_service=command.service,
                severity=command.severity,
                description=_signal_description(command),
                fingerprint=fingerprint,
            )
        )
        return IngestIncidentSignalResult(incident=created, created=True)


def _signal_description(command: IngestIncidentSignalCommand) -> str:
    lines: list[str] = []
    if command.summary:
        lines.append(command.summary)
    lines.append(f"incident.signal.v1 source={command.source}")
    if command.scenario:
        lines.append(f"scenario={command.scenario}")
    return "\n".join(lines)
