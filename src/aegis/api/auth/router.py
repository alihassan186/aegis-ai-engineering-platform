"""Dev login — issues JWTs for local testing (FR-070).

Production must use an identity provider. This route is not registered
when AEGIS_ENV=production.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from aegis.api.auth.schemas import TokenRequest, TokenResponse
from aegis.api.request_id import request_id_from
from aegis.config.settings import Settings
from aegis.infrastructure.auth.jwt import JwtNotConfiguredError, create_access_token

router = APIRouter()


@router.post("/token", response_model=TokenResponse)
def issue_dev_token(body: TokenRequest, request: Request) -> TokenResponse:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        raise JwtNotConfiguredError(
            "JWT is not configured. Set AEGIS_JWT_SECRET (never hardcode secrets)."
        )
    token = create_access_token(settings, subject=body.username, role=body.role)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expire_seconds,
        role=body.role,
        request_id=request_id_from(request),
    )
