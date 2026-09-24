"""Read investigation progress from Postgres (FR-022). The API never runs the graph."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aegis.core.protocols import (
    EvidenceRepository,
    IncidentRepository,
    InvestigationProgressRepository,
    RcaRepository,
)
from aegis.domain.evidence.entity import Evidence
from aegis.domain.incidents.entity import Incident
from aegis.domain.investigation.enums import InvestigationRunStatus, InvestigationStepStatus
from aegis.domain.investigation.progress import InvestigationProgress, InvestigationStep
from aegis.domain.rca.entity import RcaReport
from aegis.shared.exceptions import NotFoundError

GRAPH_RESUME_NOTE = (
    "Pause/resume persist a cooperative flag in Postgres. Graph resume uses "
    "thread_id plus a checkpointer; InMemorySaver is process-local, so interrupt "
    "resume only works if the worker that paused is still alive. A Postgres "
    "checkpointer is the production follow-up."
)


@dataclass(frozen=True, slots=True)
class InvestigationStepDto:
    name: str
    status: str
    detail: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class RcaVersionDto:
    version: int
    version_kind: str
    summary: str
    root_cause: str
    contributing_factors: tuple[str, ...]
    confidence: float
    status: str
    review_status: str
    evidence_citations: tuple[dict[str, str], ...]
    recommended_actions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InvestigationProgressDto:
    incident_id: UUID
    incident_state: str
    hops: int
    status: str
    paused: bool
    graph_resume_available: bool
    resume_note: str
    escalate_reason: str
    steps: tuple[InvestigationStepDto, ...]
    evidence_ids: tuple[UUID, ...]
    rca: RcaVersionDto | None
    rca_versions: tuple[RcaVersionDto, ...]


class GetInvestigationProgress:
    def __init__(
        self,
        incidents: IncidentRepository,
        evidence: EvidenceRepository,
        rca: RcaRepository,
        progress: InvestigationProgressRepository,
    ) -> None:
        self._incidents = incidents
        self._evidence = evidence
        self._rca = rca
        self._progress = progress

    async def execute(self, incident_id: UUID) -> InvestigationProgressDto:
        incident = await self._incidents.get_by_id(incident_id)
        if incident is None:
            raise NotFoundError(f"Incident '{incident_id}' was not found.")
        stored = await self._progress.get_by_incident(incident_id)
        evidence = await self._evidence.list_by_incident(incident_id)
        reports = await self._rca.list_by_incident(incident_id)
        return assemble_progress(incident, stored, evidence, reports)


def assemble_progress(
    incident: Incident,
    stored: InvestigationProgress | None,
    evidence: list[Evidence],
    reports: list[RcaReport],
) -> InvestigationProgressDto:
    versions = tuple(_rca_dto(item) for item in reports)
    steps = _step_dtos(stored, incident.id, evidence, reports)
    hops = stored.hops if stored is not None else 0
    paused = bool(stored.paused) if stored is not None else False
    status = (
        stored.status.value
        if stored is not None
        else _inferred_status(incident.state.value, reports, paused)
    )
    reason = stored.escalate_reason if stored is not None else ""
    return InvestigationProgressDto(
        incident_id=incident.id,
        incident_state=incident.state.value,
        hops=hops,
        status=status,
        paused=paused,
        graph_resume_available=False,
        resume_note=GRAPH_RESUME_NOTE,
        escalate_reason=reason,
        steps=steps,
        evidence_ids=tuple(item.id for item in evidence),
        rca=versions[-1] if versions else None,
        rca_versions=versions,
    )


def _rca_dto(report: RcaReport) -> RcaVersionDto:
    return RcaVersionDto(
        version=report.version,
        version_kind=report.version_kind.value,
        summary=report.summary,
        root_cause=report.root_cause,
        contributing_factors=report.contributing_factors,
        confidence=report.confidence,
        status=report.finding_status.value,
        review_status=report.review_status.value,
        evidence_citations=tuple(item.as_dict() for item in report.citations),
        recommended_actions=report.recommended_actions,
    )


def _step_dtos(
    stored: InvestigationProgress | None,
    incident_id: UUID,
    evidence: list[Evidence],
    reports: list[RcaReport],
) -> tuple[InvestigationStepDto, ...]:
    if stored is not None and stored.steps:
        return tuple(
            InvestigationStepDto(
                name=step.name,
                status=step.status.value,
                detail=step.detail,
                occurred_at=step.occurred_at,
            )
            for step in stored.steps
        )
    return tuple(
        InvestigationStepDto(
            name=step.name,
            status=step.status.value,
            detail=step.detail,
            occurred_at=step.occurred_at,
        )
        for step in derive_steps(incident_id, evidence, reports)
    )


def derive_steps(
    incident_id: UUID,
    evidence: list[Evidence],
    reports: list[RcaReport],
) -> list[InvestigationStep]:
    """Fallback when the worker has not persisted step rows yet."""
    by_source = {item.source.value for item in evidence}
    mapping = (
        ("observability", "simulator"),
        ("knowledge", "retrieve"),
        ("code", "code"),
        ("manual", "manual"),
    )
    steps: list[InvestigationStep] = []
    for name, source in mapping:
        if source not in by_source:
            continue
        steps.append(
            InvestigationStep.create(
                incident_id=incident_id,
                name=name,
                status=InvestigationStepStatus.COMPLETED,
                detail=f"{name} evidence recorded",
            )
        )
    if reports:
        steps.append(
            InvestigationStep.create(
                incident_id=incident_id,
                name="synthesize",
                status=InvestigationStepStatus.COMPLETED,
                detail="RCA persisted",
            )
        )
    return steps


def _inferred_status(incident_state: str, reports: list[RcaReport], paused: bool) -> str:
    if paused:
        return InvestigationRunStatus.PAUSED.value
    if reports:
        latest = reports[-1]
        if latest.review_status.value == "rejected":
            return InvestigationRunStatus.ESCALATED.value
        return InvestigationRunStatus.PENDING_REVIEW.value
    if incident_state == "investigating":
        return InvestigationRunStatus.RUNNING.value
    return InvestigationRunStatus.NOT_STARTED.value
