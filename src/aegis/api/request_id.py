"""Request correlation id (NFR-041)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response

REQUEST_ID_HEADER = "X-Request-ID"

print(f"REQUEST_ID_HEADER in request_id.py: {REQUEST_ID_HEADER}")


def request_id_from(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def add_request_id_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def _attach_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
