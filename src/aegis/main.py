"""FastAPI composition root.

Uvicorn loads this module: ``uvicorn aegis.main:app --reload``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from aegis.api.auth.router import router as auth_router
from aegis.api.errors import register_exception_handlers
from aegis.api.request_id import add_request_id_middleware
from aegis.api.router import api_v1_router
from aegis.config.settings import Settings, get_settings
from aegis.infrastructure.database.session import start_database, stop_database


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    Tests can call ``create_app()`` with explicit settings instead of
    mutating process-wide environment.
    """
    resolved = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine: AsyncEngine | None = None
        session_factory: async_sessionmaker[AsyncSession] | None = None
        if resolved.database_url:
            engine, session_factory = await start_database(resolved)
        application.state.engine = engine
        application.state.session_factory = session_factory
        try:
            yield
        finally:
            await stop_database(engine)

    application = FastAPI(
        title=resolved.app_name,
        version="0.3.0",
        description="AEGIS incident investigation API",
        debug=resolved.debug,
        lifespan=lifespan,
    )
    application.state.settings = resolved
    add_request_id_middleware(application)
    register_exception_handlers(application)
    application.include_router(_health_router())
    application.include_router(api_v1_router)
    if resolved.environment != "production":
        application.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    return application


def _health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return router


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("aegis.main:app", host="127.0.0.1", port=8000, reload=get_settings().debug)
