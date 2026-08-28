"""FastAPI composition root.

Uvicorn loads this module: ``uvicorn aegis.main:app --reload``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

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
        version="0.1.0",
        description="AEGIS bootstrap foundation",
        debug=resolved.debug,
        lifespan=lifespan,
    )
    application.state.settings = resolved
    application.include_router(_health_router())
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
