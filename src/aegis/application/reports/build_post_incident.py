"""Assemble a post-incident report (FR-101). No LLM. No OpenSearch.

A human can save the markdown as ``docs/knowledge/incidents/INC-….md``
and reindex with Step 3.6. This module must not write the knowledge index.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from aegis.application.security.redact import redact_for_llm
from aegis.core.protocols import (
    EvidenceRepository,
    IncidentRepository,
    InvestigationProgressRepository,
    NotificationRepository,
    RcaRepository,
)
from aegis.domain.incidents.enums import IncidentState
from aegis.shared.exceptions import NotFoundError, ValidationError

_REPORTABLE = frozenset({IncidentState.IDENTIFIED, IncidentState.CLOSED})


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    at: datetime
    kind: str
    detail: str


@dataclass(frozen=True, slots=True)
class EvidenceEntry:
    id: UUID
    source: str
    kind: str
    summary: str


@dataclass(frozen=True, slots=True)
class RcaEntry:
    version: int
    version_kind: str
    review_status: str
    summary: str
    root_cause: str
    recommended_actions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NotificationEntry:
    kind: str
    reason: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PostIncidentReport:
    incident_id: UUID
    title: str
    service: str
    severity: str
    state: str
    timeline: tuple[TimelineEntry, ...]
    evidence: tuple[EvidenceEntry, ...]
    rca_versions: tuple[RcaEntry, ...]
    accepted_root_cause: str | None
    recommended_actions: tuple[str, ...]
    notifications: tuple[NotificationEntry, ...]
    markdown: str


class BuildPostIncidentReport:
    def __init__(
        self,
        incidents: IncidentRepository,
        evidence: EvidenceRepository,
        rca: RcaRepository,
        progress: InvestigationProgressRepository,
        notifications: NotificationRepository,
    ) -> None:
        self._incidents = incidents
        self._evidence = evidence
        self._rca = rca
        self._progress = progress
        self._notifications = notifications

    async def execute(self, incident_id: UUID) -> PostIncidentReport:
        incident = await self._incidents.get_by_id(incident_id)
        if incident is None:
            raise NotFoundError(f"Incident '{incident_id}' was not found.")
        if incident.state not in _REPORTABLE:
            raise ValidationError(
                "Post-incident report is available after identified or closed."
            )
        evidence = await self._evidence.list_by_incident(incident_id)
        reports = await self._rca.list_by_incident(incident_id)
        stored = await self._progress.get_by_incident(incident_id)
        notes = await self._notifications.list_by_incident(incident_id)

        timeline: list[TimelineEntry] = [
            TimelineEntry(
                at=step.occurred_at,
                kind="state",
                detail=f"{step.from_state.value} → {step.to_state.value}",
            )
            for step in incident.state_history
        ]
        if stored is not None:
            for step in stored.steps:
                timeline.append(
                    TimelineEntry(
                        at=step.occurred_at,
                        kind="investigation",
                        detail=f"{step.name} {step.status.value}",
                    )
                )
        timeline.sort(key=lambda item: item.at)

        evidence_rows = tuple(
            EvidenceEntry(
                id=item.id,
                source=item.source.value,
                kind=item.kind.value,
                summary=redact_for_llm(item.summary),
            )
            for item in evidence
        )
        rca_rows = tuple(
            RcaEntry(
                version=item.version,
                version_kind=item.version_kind.value,
                review_status=item.review_status.value,
                summary=redact_for_llm(item.summary),
                root_cause=redact_for_llm(item.root_cause),
                recommended_actions=item.recommended_actions,
            )
            for item in reports
        )
        accepted = next(
            (item for item in reversed(rca_rows) if item.review_status == "accepted"),
            None,
        )
        actions = accepted.recommended_actions if accepted is not None else ()
        notify_rows = tuple(
            NotificationEntry(
                kind=item.kind.value,
                reason=item.reason,
                created_at=item.created_at,
            )
            for item in notes
        )
        report = PostIncidentReport(
            incident_id=incident.id,
            title=incident.title,
            service=incident.affected_service,
            severity=incident.severity.value,
            state=incident.state.value,
            timeline=tuple(timeline),
            evidence=evidence_rows,
            rca_versions=rca_rows,
            accepted_root_cause=accepted.root_cause if accepted else None,
            recommended_actions=actions,
            notifications=notify_rows,
            markdown="",
        )
        return PostIncidentReport(
            incident_id=report.incident_id,
            title=report.title,
            service=report.service,
            severity=report.severity,
            state=report.state,
            timeline=report.timeline,
            evidence=report.evidence,
            rca_versions=report.rca_versions,
            accepted_root_cause=report.accepted_root_cause,
            recommended_actions=report.recommended_actions,
            notifications=report.notifications,
            markdown=render_markdown(report),
        )


def render_markdown(report: PostIncidentReport) -> str:
    lines = [
        f"# Post-incident report — {report.title}",
        "",
        f"- incident_id: `{report.incident_id}`",
        f"- service: {report.service}",
        f"- severity: {report.severity}",
        f"- state: {report.state}",
        "",
        "## Timeline",
    ]
    if report.timeline:
        for item in report.timeline:
            lines.append(f"- {item.at.isoformat()} [{item.kind}] {item.detail}")
    else:
        lines.append("- (empty)")
    lines.extend(["", "## Evidence"])
    if report.evidence:
        for item in report.evidence:
            lines.append(f"- `{item.id}` ({item.source}/{item.kind}) {item.summary}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## RCA"])
    if report.accepted_root_cause:
        lines.append(f"Accepted root cause: {report.accepted_root_cause}")
    for item in report.rca_versions:
        lines.append(
            f"- v{item.version} {item.version_kind} [{item.review_status}] {item.summary}"
        )
    lines.extend(["", "## Recommended actions"])
    if report.recommended_actions:
        for action in report.recommended_actions:
            lines.append(f"- {action}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Notifications"])
    if report.notifications:
        for item in report.notifications:
            lines.append(f"- {item.created_at.isoformat()} {item.kind} ({item.reason})")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append(
        "This report is not indexed. Curate markdown under "
        "`docs/knowledge/incidents/` then run Step 3.6 ingest."
    )
    return "\n".join(lines)
