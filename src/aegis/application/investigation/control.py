"""Pause and resume flags (FR-023). Does not SIGKILL the worker."""

from __future__ import annotations

from uuid import UUID

from aegis.application.investigation.get_progress import (
    GetInvestigationProgress,
    InvestigationProgressDto,
)
from aegis.core.protocols import IncidentRepository, InvestigationProgressRepository
from aegis.domain.incidents.enums import IncidentState
from aegis.domain.investigation.progress import InvestigationProgress
from aegis.shared.exceptions import NotFoundError, ValidationError


class ControlInvestigation:
    def __init__(
        self,
        incidents: IncidentRepository,
        progress: InvestigationProgressRepository,
        get_progress: GetInvestigationProgress,
    ) -> None:
        self._incidents = incidents
        self._progress = progress
        self._get_progress = get_progress

    async def pause(self, incident_id: UUID) -> InvestigationProgressDto:
        await self._require_investigating(incident_id)
        stored = await self._progress.get_by_incident(incident_id)
        base = stored or InvestigationProgress.create(incident_id=incident_id)
        if not base.paused:
            await self._progress.save(base.with_pause(True))
        return await self._get_progress.execute(incident_id)

    async def resume(self, incident_id: UUID) -> InvestigationProgressDto:
        await self._require_investigating(incident_id)
        stored = await self._progress.get_by_incident(incident_id)
        base = stored or InvestigationProgress.create(incident_id=incident_id)
        if base.paused:
            await self._progress.save(base.with_pause(False))
        return await self._get_progress.execute(incident_id)

    async def _require_investigating(self, incident_id: UUID) -> None:
        incident = await self._incidents.get_by_id(incident_id)
        if incident is None:
            raise NotFoundError(f"Incident '{incident_id}' was not found.")
        if incident.state is not IncidentState.INVESTIGATING:
            raise ValidationError("Pause and resume apply only while investigating.")
