"""HTTP exception handlers. Error body matches system-boundaries §4."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from aegis.api.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DatabaseNotConfiguredError,
    WebhookNotConfiguredError,
)
from aegis.api.request_id import request_id_from
from aegis.domain.incidents.exceptions import InvalidTransitionError
from aegis.infrastructure.auth.jwt import JwtNotConfiguredError
from aegis.shared.exceptions import NotFoundError, ValidationError


def error_body(request: Request, code: str, message: str) -> dict[str, dict[str, str]]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id_from(request),
        }
    }


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(AuthenticationError)
    async def authentication_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        headers = {"WWW-Authenticate": exc.challenge} if exc.challenge else None
        return JSONResponse(
            status_code=401,
            content=error_body(request, "UNAUTHENTICATED", str(exc)),
            headers=headers,
        )

    @application.exception_handler(WebhookNotConfiguredError)
    async def webhook_not_configured_handler(
        request: Request,
        exc: WebhookNotConfiguredError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=error_body(request, "WEBHOOK_NOT_CONFIGURED", str(exc)),
        )

    @application.exception_handler(AuthorizationError)
    async def authorization_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=error_body(request, "FORBIDDEN", str(exc)),
        )

    @application.exception_handler(JwtNotConfiguredError)
    async def jwt_not_configured_handler(
        request: Request,
        exc: JwtNotConfiguredError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=error_body(request, "AUTH_NOT_CONFIGURED", str(exc)),
        )

    @application.exception_handler(DatabaseNotConfiguredError)
    async def database_not_configured_handler(
        request: Request,
        exc: DatabaseNotConfiguredError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=error_body(request, "DATABASE_NOT_CONFIGURED", str(exc)),
        )

    @application.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content=error_body(request, "NOT_FOUND", str(exc)))

    @application.exception_handler(InvalidTransitionError)
    async def invalid_transition_handler(
        request: Request,
        exc: InvalidTransitionError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=error_body(request, "INVALID_TRANSITION", str(exc)),
        )

    @application.exception_handler(ValidationError)
    async def domain_validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body(request, "VALIDATION_ERROR", str(exc)),
        )

    @application.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        messages = "; ".join(
            f"{'.'.join(str(part) for part in err.get('loc', ()))}: {err.get('msg')}"
            for err in exc.errors()
        )
        return JSONResponse(
            status_code=422,
            content=error_body(request, "VALIDATION_ERROR", messages),
        )
