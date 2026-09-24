"""Accept, reject, or amend an RCA (FR-034, FR-035). Does not run the graph."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from aegis.application.investigation.get_progress import (
    GetInvestigationProgress,
    InvestigationProgressDto,
)
from aegis.application.notifications.notify import NotifyInvestigation, notify_best_effort
from aegis.core.protocols import (
    IncidentRepository,
    InvestigationProgressRepository,
    RcaRepository,
)
from aegis.domain.incidents.entity import Incident
from aegis.domain.incidents.enums import IncidentState
from aegis.domain.investigation.progress import InvestigationProgress
from aegis.domain.rca.entity import RcaCitation, RcaReport
from aegis.domain.rca.enums import RcaFindingStatus, RcaReviewStatus, RcaVersionKind
from aegis.shared.exceptions import NotFoundError, ValidationError


@dataclass(frozen=True, slots=True)
class AmendRcaCommand:
    summary: str
    root_cause: str
    contributing_factors: Sequence[str]
    confidence: float
    status: str
    recommended_actions: Sequence[str]
    evidence_citations: Sequence[RcaCitation] | None = None


class TransitionRca:
    def __init__(
        self,
        incidents: IncidentRepository,
        rca: RcaRepository,
        progress: InvestigationProgressRepository,
        get_progress: GetInvestigationProgress,
        notify: NotifyInvestigation | None = None,
    ) -> None:
        self._incidents = incidents
        self._rca = rca
        self._progress = progress
        self._get_progress = get_progress
        self._notify = notify

    async def accept(self, incident_id: UUID) -> InvestigationProgressDto:
        incident, reports = await self._require_incident_and_reports(incident_id)
        latest = reports[-1]
        accepted = latest.with_review_status(RcaReviewStatus.ACCEPTED)
        if accepted is not latest:
            await self._rca.save(accepted)
        if incident.state is IncidentState.INVESTIGATING:
            incident.transition_to(IncidentState.IDENTIFIED)
            await self._incidents.save(incident)
        return await self._get_progress.execute(incident_id)

    async def reject(self, incident_id: UUID) -> InvestigationProgressDto:
        incident, reports = await self._require_incident_and_reports(incident_id)
        latest = reports[-1]
        rejected = latest.with_review_status(RcaReviewStatus.REJECTED)
        if rejected is not latest:
            await self._rca.save(rejected)
        stored = await self._progress.get_by_incident(incident_id)
        base = stored or InvestigationProgress.create(incident_id=incident_id)
        await self._progress.save(base.with_rejection())
        await notify_best_effort(self._notify, incident=incident, escalate_reason="rca_rejected")
        return await self._get_progress.execute(incident_id)

    async def amend(self, incident_id: UUID, command: AmendRcaCommand) -> InvestigationProgressDto:
        _incident, reports = await self._require_incident_and_reports(incident_id)
        latest = reports[-1]
        citations = list(command.evidence_citations or latest.citations)
        if not citations:
            raise ValidationError("Amended RCA must cite at least one evidence_id.")
        try:
            finding = RcaFindingStatus(command.status)
        except ValueError as exc:
            raise ValidationError("status must be 'confirmed' or 'hypothesis'.") from exc
        amended = RcaReport.create(
            incident_id=incident_id,
            summary=command.summary,
            root_cause=command.root_cause,
            contributing_factors=command.contributing_factors,
            confidence=command.confidence,
            finding_status=finding,
            citations=citations,
            recommended_actions=command.recommended_actions,
            model_id="human-amendment",
            version=latest.version + 1,
            version_kind=RcaVersionKind.AMENDED,
            review_status=RcaReviewStatus.PENDING_REVIEW,
        )
        await self._rca.add(amended)
        await notify_best_effort(self._notify, incident=_incident, report=amended)
        return await self._get_progress.execute(incident_id)

    async def _require_incident_and_reports(
        self,
        incident_id: UUID,
    ) -> tuple[Incident, list[RcaReport]]:
        incident = await self._incidents.get_by_id(incident_id)
        if incident is None:
            raise NotFoundError(f"Incident '{incident_id}' was not found.")
        reports = await self._rca.list_by_incident(incident_id)
        if not reports:
            raise ValidationError("No RCA exists for this investigation.")
        return incident, reports
