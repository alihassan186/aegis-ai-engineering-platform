"""Ingest an incident.signal.v1 webhook by reusing Incident.create (FR-113)."""

from __future__ import annotations

from aegis.application.incidents.create_incident import CreateIncident
from aegis.application.incidents.dto import (
    CreateIncidentCommand,
    IncidentDto,
    IngestIncidentSignalCommand,
)


class IngestIncidentSignal:
    def __init__(self, create_incident: CreateIncident) -> None:
        self._create_incident = create_incident

    async def execute(self, command: IngestIncidentSignalCommand) -> IncidentDto:
        return await self._create_incident.execute(
            CreateIncidentCommand(
                title=command.title,
                affected_service=command.service,
                severity=command.severity,
                description=_signal_description(command),
            )
        )


def _signal_description(command: IngestIncidentSignalCommand) -> str:
    lines: list[str] = []
    if command.summary:
        lines.append(command.summary)
    lines.append(f"incident.signal.v1 source={command.source}")
    if command.scenario:
        lines.append(f"scenario={command.scenario}")
    if command.fingerprint:
        lines.append(f"fingerprint={command.fingerprint}")
    return "\n".join(lines)
