"""HTTP schemas for investigation progress. No prompts or embeddings."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from aegis.api.incidents.schemas import ErrorResponse
from aegis.application.investigation.get_progress import (
    InvestigationProgressDto,
    RcaVersionDto,
)


class InvestigationStepBody(BaseModel):
    name: str
    status: str
    detail: str
    occurred_at: datetime


class RcaCitationBody(BaseModel):
    evidence_id: UUID
    source: str
    relevance: str


class RcaVersionBody(BaseModel):
    version: int
    version_kind: str
    summary: str
    root_cause: str
    contributing_factors: list[str]
    confidence: float
    status: str
    review_status: str
    evidence_citations: list[RcaCitationBody]
    recommended_actions: list[str]


class InvestigationProgressResponse(BaseModel):
    incident_id: UUID
    incident_state: str
    hops: int
    status: str
    paused: bool
    graph_resume_available: bool
    resume_note: str
    escalate_reason: str
    steps: list[InvestigationStepBody]
    evidence_ids: list[UUID]
    rca: RcaVersionBody | None
    rca_versions: list[RcaVersionBody]
    request_id: str


class AmendRcaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    root_cause: str = Field(min_length=1)
    contributing_factors: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    status: str = Field(pattern="^(confirmed|hypothesis)$")
    recommended_actions: list[str] = Field(default_factory=list)
    evidence_citations: list[RcaCitationBody] | None = None


class ManualEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=800)
    content_ref: str = Field(default="manual:note", max_length=1024)


class ManualEvidenceResponse(BaseModel):
    id: UUID
    source: str
    kind: str
    summary: str
    request_id: str


def progress_response_from_dto(
    dto: InvestigationProgressDto,
    request_id: str,
) -> InvestigationProgressResponse:
    versions = [_rca_body(item) for item in dto.rca_versions]
    return InvestigationProgressResponse(
        incident_id=dto.incident_id,
        incident_state=dto.incident_state,
        hops=dto.hops,
        status=dto.status,
        paused=dto.paused,
        graph_resume_available=dto.graph_resume_available,
        resume_note=dto.resume_note,
        escalate_reason=dto.escalate_reason,
        steps=[
            InvestigationStepBody(
                name=step.name,
                status=step.status,
                detail=step.detail,
                occurred_at=step.occurred_at,
            )
            for step in dto.steps
        ],
        evidence_ids=list(dto.evidence_ids),
        rca=_rca_body(dto.rca) if dto.rca is not None else None,
        rca_versions=versions,
        request_id=request_id,
    )


def _rca_body(item: RcaVersionDto) -> RcaVersionBody:
    return RcaVersionBody(
        version=item.version,
        version_kind=item.version_kind,
        summary=item.summary,
        root_cause=item.root_cause,
        contributing_factors=list(item.contributing_factors),
        confidence=item.confidence,
        status=item.status,
        review_status=item.review_status,
        evidence_citations=[
            RcaCitationBody(
                evidence_id=UUID(str(cite["evidence_id"])),
                source=cite["source"],
                relevance=cite["relevance"],
            )
            for cite in item.evidence_citations
        ],
        recommended_actions=list(item.recommended_actions),
    )


__all__ = [
    "AmendRcaRequest",
    "ErrorResponse",
    "InvestigationProgressResponse",
    "ManualEvidenceRequest",
    "ManualEvidenceResponse",
]
