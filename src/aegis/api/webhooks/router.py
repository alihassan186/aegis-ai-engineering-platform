"""Webhook ingest routes. Authenticity is HMAC, not human JWT (THR-002)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError

from aegis.api.dependencies import get_ingest_incident_signal
from aegis.api.exceptions import AuthenticationError, WebhookNotConfiguredError
from aegis.api.incidents.schemas import ErrorResponse, IncidentResponse, incident_response_from_dto
from aegis.api.request_id import request_id_from
from aegis.api.webhooks.schemas import IncidentSignalRequest
from aegis.api.webhooks.signature import SIGNATURE_HEADER, verify_signature
from aegis.application.incidents.dto import IngestIncidentSignalCommand
from aegis.application.incidents.ingest_signal import IngestIncidentSignal
from aegis.config.settings import Settings


async def require_webhook_signature(request: Request) -> None:
    """Reject unsigned or forged bodies before a database session (THR-002).

    IP allowlisting from THR-002 is deferred.
    """
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings) or not settings.webhook_secret.strip():
        raise WebhookNotConfiguredError(
            "Webhook is not configured. Set AEGIS_WEBHOOK_SECRET (never hardcode secrets)."
        )
    raw = await request.body()
    provided = request.headers.get(SIGNATURE_HEADER, "")
    if not verify_signature(settings.webhook_secret, raw, provided):
        raise AuthenticationError("Invalid webhook signature.", challenge=None)


router = APIRouter(dependencies=[Depends(require_webhook_signature)])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


@router.post(
    "/incidents",
    status_code=status.HTTP_201_CREATED,
    response_model=IncidentResponse,
    responses=_ERROR_RESPONSES,
)
async def ingest_incident_signal(
    request: Request,
    response: Response,
    use_case: IngestIncidentSignal = Depends(get_ingest_incident_signal),
) -> IncidentResponse:
    raw = await request.body()
    try:
        body = IncidentSignalRequest.model_validate_json(raw)
    except PydanticValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    dto = await use_case.execute(
        IngestIncidentSignalCommand(
            source=body.source,
            service=body.service,
            title=body.title,
            severity=body.severity,
            summary=body.summary,
            scenario=body.scenario,
            fingerprint=body.fingerprint,
        )
    )
    request_id = request_id_from(request)
    response.headers["Location"] = f"/api/v1/incidents/{dto.id}"
    return incident_response_from_dto(dto, request_id)
