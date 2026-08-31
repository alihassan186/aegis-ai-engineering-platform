"""Simulator process entry (FR-080 skeleton).

Run separately from AEGIS::

    uv run uvicorn apps.simulator.main:app --host 127.0.0.1 --port 8001
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from apps.simulator.config import Settings, get_settings
from apps.simulator.services import ServiceId, ServiceRuntime, ServiceStatus

BOOT_MESSAGE = "simulator boot"


class ServiceResponse(BaseModel):
    id: ServiceId
    display_name: str
    depends_on: list[ServiceId]
    status: ServiceStatus


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.boot_message = BOOT_MESSAGE
        application.state.runtime = ServiceRuntime()
        yield

    application = FastAPI(
        title=resolved.app_name,
        version="0.3.0",
        description="AEGIS production simulator (dev/test)",
        debug=resolved.debug,
        lifespan=lifespan,
    )
    application.state.settings = resolved

    @application.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok", "app": resolved.app_name}

    @application.get("/services", response_model=list[ServiceResponse])
    def list_services() -> list[ServiceResponse]:
        runtime: ServiceRuntime = application.state.runtime
        return [
            ServiceResponse(
                id=row.spec.id,
                display_name=row.spec.display_name,
                depends_on=sorted(row.spec.depends_on),
                status=row.status,
            )
            for row in runtime.list_snapshots()
        ]

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    _settings = get_settings()
    uvicorn.run(
        "apps.simulator.main:app",
        host=_settings.host,
        port=_settings.port,
        reload=_settings.debug,
    )
