"""GET /api/v1/incidents/{id}/report — JWT, same read RBAC as investigation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from aegis.api.dependencies import (
    CurrentUser,
    get_build_report,
    get_current_user,
    require_permission,
)
from aegis.api.reports.schemas import (
    ErrorResponse,
    PostIncidentReportResponse,
    report_response_from_dto,
)
from aegis.api.request_id import request_id_from
from aegis.application.reports.build_post_incident import BuildPostIncidentReport
from aegis.domain.auth.permissions import Permission

router = APIRouter(dependencies=[Depends(get_current_user)])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.get(
    "",
    response_model=PostIncidentReportResponse,
    responses=_ERROR_RESPONSES,
    summary="Get post-incident report (not auto-indexed)",
)
async def get_post_incident_report(
    id: UUID,
    request: Request,
    _user: CurrentUser = Depends(require_permission(Permission.VIEW_INVESTIGATION)),
    use_case: BuildPostIncidentReport = Depends(get_build_report),
) -> PostIncidentReportResponse:
    dto = await use_case.execute(id)
    return report_response_from_dto(dto, request_id_from(request))
