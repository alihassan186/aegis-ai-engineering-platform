"""JWT investigation progress, pause/resume, RCA review, and manual evidence."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from aegis.api.dependencies import (
    CurrentUser,
    get_control_investigation,
    get_current_user,
    get_investigation_progress,
    get_record_evidence,
    get_transition_rca,
    require_permission,
)
from aegis.api.investigations.schemas import (
    AmendRcaRequest,
    ErrorResponse,
    InvestigationProgressResponse,
    ManualEvidenceRequest,
    ManualEvidenceResponse,
    progress_response_from_dto,
)
from aegis.api.request_id import request_id_from
from aegis.application.evidence.record_evidence import RecordEvidence
from aegis.application.investigation.control import ControlInvestigation
from aegis.application.investigation.get_progress import GetInvestigationProgress
from aegis.application.investigation.transition_rca import AmendRcaCommand, TransitionRca
from aegis.domain.auth.permissions import Permission
from aegis.domain.evidence.enums import EvidenceKind, EvidenceSource
from aegis.domain.rca.entity import RcaCitation

router = APIRouter(dependencies=[Depends(get_current_user)])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.get(
    "",
    response_model=InvestigationProgressResponse,
    responses=_ERROR_RESPONSES,
    summary="Get investigation progress",
)
async def get_investigation(
    id: UUID,
    request: Request,
    _user: CurrentUser = Depends(require_permission(Permission.VIEW_INVESTIGATION)),
    use_case: GetInvestigationProgress = Depends(get_investigation_progress),
) -> InvestigationProgressResponse:
    dto = await use_case.execute(id)
    return progress_response_from_dto(dto, request_id_from(request))


@router.post(
    "/pause",
    response_model=InvestigationProgressResponse,
    responses=_ERROR_RESPONSES,
    summary="Pause investigation (cooperative flag)",
)
async def pause_investigation(
    id: UUID,
    request: Request,
    _user: CurrentUser = Depends(require_permission(Permission.CONTROL_INVESTIGATION)),
    use_case: ControlInvestigation = Depends(get_control_investigation),
) -> InvestigationProgressResponse:
    dto = await use_case.pause(id)
    return progress_response_from_dto(dto, request_id_from(request))


@router.post(
    "/resume",
    response_model=InvestigationProgressResponse,
    responses=_ERROR_RESPONSES,
    summary="Resume investigation flag (InMemorySaver is not durable)",
)
async def resume_investigation(
    id: UUID,
    request: Request,
    _user: CurrentUser = Depends(require_permission(Permission.CONTROL_INVESTIGATION)),
    use_case: ControlInvestigation = Depends(get_control_investigation),
) -> InvestigationProgressResponse:
    dto = await use_case.resume(id)
    return progress_response_from_dto(dto, request_id_from(request))


@router.post(
    "/rca/accept",
    response_model=InvestigationProgressResponse,
    responses=_ERROR_RESPONSES,
    summary="Accept RCA and move incident to identified",
)
async def accept_rca(
    id: UUID,
    request: Request,
    _user: CurrentUser = Depends(require_permission(Permission.REVIEW_RCA)),
    use_case: TransitionRca = Depends(get_transition_rca),
) -> InvestigationProgressResponse:
    dto = await use_case.accept(id)
    return progress_response_from_dto(dto, request_id_from(request))


@router.post(
    "/rca/reject",
    response_model=InvestigationProgressResponse,
    responses=_ERROR_RESPONSES,
    summary="Reject RCA and stay investigating",
)
async def reject_rca(
    id: UUID,
    request: Request,
    _user: CurrentUser = Depends(require_permission(Permission.REVIEW_RCA)),
    use_case: TransitionRca = Depends(get_transition_rca),
) -> InvestigationProgressResponse:
    dto = await use_case.reject(id)
    return progress_response_from_dto(dto, request_id_from(request))


@router.post(
    "/rca/amend",
    response_model=InvestigationProgressResponse,
    responses=_ERROR_RESPONSES,
    summary="Store an amended RCA version (keep original)",
)
async def amend_rca(
    id: UUID,
    body: AmendRcaRequest,
    request: Request,
    _user: CurrentUser = Depends(require_permission(Permission.REVIEW_RCA)),
    use_case: TransitionRca = Depends(get_transition_rca),
) -> InvestigationProgressResponse:
    citations = None
    if body.evidence_citations is not None:
        citations = [
            RcaCitation(
                evidence_id=item.evidence_id,
                source=item.source,
                relevance=item.relevance,
            )
            for item in body.evidence_citations
        ]
    dto = await use_case.amend(
        id,
        AmendRcaCommand(
            summary=body.summary,
            root_cause=body.root_cause,
            contributing_factors=body.contributing_factors,
            confidence=body.confidence,
            status=body.status,
            recommended_actions=body.recommended_actions,
            evidence_citations=citations,
        ),
    )
    return progress_response_from_dto(dto, request_id_from(request))


@router.post(
    "/evidence",
    status_code=status.HTTP_201_CREATED,
    response_model=ManualEvidenceResponse,
    responses=_ERROR_RESPONSES,
    summary="Add a manual evidence note (FR-024)",
)
async def add_manual_evidence(
    id: UUID,
    body: ManualEvidenceRequest,
    request: Request,
    _user: CurrentUser = Depends(require_permission(Permission.ADD_EVIDENCE)),
    use_case: RecordEvidence = Depends(get_record_evidence),
    get_incident: GetInvestigationProgress = Depends(get_investigation_progress),
) -> ManualEvidenceResponse:
    await get_incident.execute(id)
    evidence = await use_case.execute(
        incident_id=id,
        source=EvidenceSource.MANUAL,
        kind=EvidenceKind.NOTE,
        content_ref=body.content_ref,
        summary=body.summary,
        metadata={"tool": "manual"},
    )
    return ManualEvidenceResponse(
        id=evidence.id,
        source=evidence.source.value,
        kind=evidence.kind.value,
        summary=evidence.summary,
        request_id=request_id_from(request),
    )
