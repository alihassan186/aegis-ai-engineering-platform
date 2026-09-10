"""POST /api/v1/retrieve — JWT knowledge search with citations. Not HMAC."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status

from aegis.api.dependencies import (
    CurrentUser,
    get_current_user,
    get_retrieve_knowledge,
    require_permission,
)
from aegis.api.rag.schemas import (
    ErrorResponse,
    RetrieveRequest,
    RetrieveResponse,
    retrieve_response_from_result,
)
from aegis.api.request_id import request_id_from
from aegis.application.rag.retrieve import RetrieveFilters, RetrieveKnowledge
from aegis.domain.auth.permissions import Permission

router = APIRouter(dependencies=[Depends(get_current_user)])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


@router.post(
    "/retrieve",
    response_model=RetrieveResponse,
    status_code=status.HTTP_200_OK,
    responses=_ERROR_RESPONSES,
    summary="Retrieve knowledge chunks with citations",
)
def retrieve_knowledge(
    body: RetrieveRequest,
    request: Request,
    _user: CurrentUser = Depends(require_permission(Permission.RETRIEVE_KNOWLEDGE)),
    use_case: RetrieveKnowledge = Depends(get_retrieve_knowledge),
) -> RetrieveResponse:
    filters = None
    if body.filters is not None:
        filters = RetrieveFilters(
            service=body.filters.service,
            doc_type=body.filters.doc_type,
            scenario=body.filters.scenario,
            date_from=body.filters.date_from,
            date_to=body.filters.date_to,
            incident_id=body.filters.incident_id,
        )
    result = use_case.execute(body.query, filters=filters, top_k=body.top_k)
    return retrieve_response_from_result(result, request_id_from(request))
