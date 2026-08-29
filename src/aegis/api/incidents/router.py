"""Incident HTTP routes — thin adapters over application use cases."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from aegis.api.dependencies import (
    get_create_incident,
    get_get_incident,
    get_list_incidents,
    get_transition_incident,
)
from aegis.api.incidents.schemas import (
    CreateIncidentRequest,
    ErrorResponse,
    IncidentListResponse,
    IncidentResponse,
    TransitionStateRequest,
    incident_body_from_dto,
    incident_response_from_dto,
)
from aegis.api.request_id import request_id_from
from aegis.application.incidents import (
    CreateIncident,
    CreateIncidentCommand,
    GetIncident,
    ListIncidents,
    ListIncidentsQuery,
    TransitionIncident,
    TransitionIncidentCommand,
)
from aegis.domain.incidents.enums import IncidentState, Severity

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=IncidentResponse,
    responses=_ERROR_RESPONSES,
)
async def create_incident(
    body: CreateIncidentRequest,
    request: Request,
    response: Response,
    use_case: CreateIncident = Depends(get_create_incident),
) -> IncidentResponse:
    dto = await use_case.execute(
        CreateIncidentCommand(
            title=body.title,
            affected_service=body.affected_service,
            severity=body.severity,
            description=body.description,
            owner_id=body.owner_id,
        )
    )
    request_id = request_id_from(request)
    response.headers["Location"] = f"/api/v1/incidents/{dto.id}"
    return incident_response_from_dto(dto, request_id)


@router.get(
    "",
    response_model=IncidentListResponse,
    responses=_ERROR_RESPONSES,
)
async def list_incidents(
    request: Request,
    use_case: ListIncidents = Depends(get_list_incidents),
    state: IncidentState | None = Query(default=None),
    severity: Severity | None = Query(default=None),
    affected_service: str | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    created_after: datetime | None = Query(default=None),
    created_before: datetime | None = Query(default=None),
) -> IncidentListResponse:
    dtos = await use_case.execute(
        ListIncidentsQuery(
            state=state,
            severity=severity,
            affected_service=affected_service,
            owner_id=owner_id,
            created_after=created_after,
            created_before=created_before,
        )
    )
    return IncidentListResponse(
        items=[incident_body_from_dto(dto) for dto in dtos],
        request_id=request_id_from(request),
    )


@router.get(
    "/{id}",
    response_model=IncidentResponse,
    responses=_ERROR_RESPONSES,
)
async def get_incident(
    id: UUID,
    request: Request,
    use_case: GetIncident = Depends(get_get_incident),
) -> IncidentResponse:
    dto = await use_case.execute(id)
    return incident_response_from_dto(dto, request_id_from(request))


@router.patch(
    "/{id}/state",
    response_model=IncidentResponse,
    responses=_ERROR_RESPONSES,
)
async def transition_incident_state(
    id: UUID,
    body: TransitionStateRequest,
    request: Request,
    use_case: TransitionIncident = Depends(get_transition_incident),
) -> IncidentResponse:
    dto = await use_case.execute(TransitionIncidentCommand(incident_id=id, new_state=body.state))
    return incident_response_from_dto(dto, request_id_from(request))
