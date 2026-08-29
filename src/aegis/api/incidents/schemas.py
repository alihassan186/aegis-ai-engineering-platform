"""Pydantic HTTP schemas. Separate from domain entities and application DTOs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from aegis.application.incidents.dto import IncidentDto
from aegis.domain.incidents.enums import IncidentState, Severity


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class CreateIncidentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=512)
    affected_service: str = Field(min_length=1, max_length=255)
    severity: Severity
    description: str | None = None
    owner_id: UUID | None = None


class TransitionStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: IncidentState


class StateTransitionResponse(BaseModel):
    from_state: IncidentState
    to_state: IncidentState
    occurred_at: datetime


class IncidentBody(BaseModel):
    id: UUID
    title: str
    description: str | None
    state: IncidentState
    severity: Severity
    affected_service: str
    owner_id: UUID | None
    created_at: datetime
    updated_at: datetime
    state_history: list[StateTransitionResponse]


class IncidentResponse(IncidentBody):
    request_id: str


class IncidentListResponse(BaseModel):
    items: list[IncidentBody]
    request_id: str


def incident_body_from_dto(dto: IncidentDto) -> IncidentBody:
    return IncidentBody(
        id=dto.id,
        title=dto.title,
        description=dto.description,
        state=dto.state,
        severity=dto.severity,
        affected_service=dto.affected_service,
        owner_id=dto.owner_id,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
        state_history=[
            StateTransitionResponse(
                from_state=step.from_state,
                to_state=step.to_state,
                occurred_at=step.occurred_at,
            )
            for step in dto.state_history
        ],
    )


def incident_response_from_dto(dto: IncidentDto, request_id: str) -> IncidentResponse:
    body = incident_body_from_dto(dto)
    return IncidentResponse(**body.model_dump(), request_id=request_id)
