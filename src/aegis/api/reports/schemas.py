"""HTTP schemas for the post-incident report. No embeddings."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from aegis.api.incidents.schemas import ErrorResponse
from aegis.application.reports.build_post_incident import PostIncidentReport


class TimelineBody(BaseModel):
    at: datetime
    kind: str
    detail: str


class EvidenceBody(BaseModel):
    id: UUID
    source: str
    kind: str
    summary: str


class RcaBody(BaseModel):
    version: int
    version_kind: str
    review_status: str
    summary: str
    root_cause: str
    recommended_actions: list[str]


class NotificationBody(BaseModel):
    kind: str
    reason: str
    created_at: datetime


class PostIncidentReportResponse(BaseModel):
    incident_id: UUID
    title: str
    service: str
    severity: str
    state: str
    timeline: list[TimelineBody]
    evidence: list[EvidenceBody]
    rca_versions: list[RcaBody]
    accepted_root_cause: str | None
    recommended_actions: list[str]
    notifications: list[NotificationBody]
    markdown: str
    request_id: str


def report_response_from_dto(
    dto: PostIncidentReport,
    request_id: str,
) -> PostIncidentReportResponse:
    return PostIncidentReportResponse(
        incident_id=dto.incident_id,
        title=dto.title,
        service=dto.service,
        severity=dto.severity,
        state=dto.state,
        timeline=[
            TimelineBody(at=item.at, kind=item.kind, detail=item.detail)
            for item in dto.timeline
        ],
        evidence=[
            EvidenceBody(
                id=item.id,
                source=item.source,
                kind=item.kind,
                summary=item.summary,
            )
            for item in dto.evidence
        ],
        rca_versions=[
            RcaBody(
                version=item.version,
                version_kind=item.version_kind,
                review_status=item.review_status,
                summary=item.summary,
                root_cause=item.root_cause,
                recommended_actions=list(item.recommended_actions),
            )
            for item in dto.rca_versions
        ],
        accepted_root_cause=dto.accepted_root_cause,
        recommended_actions=list(dto.recommended_actions),
        notifications=[
            NotificationBody(kind=item.kind, reason=item.reason, created_at=item.created_at)
            for item in dto.notifications
        ],
        markdown=dto.markdown,
        request_id=request_id,
    )


__all__ = ["ErrorResponse", "PostIncidentReportResponse", "report_response_from_dto"]
