"""FastAPI composition root.

Uvicorn loads this module: ``uvicorn aegis.main:app --reload``.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

from aegis.config.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application.

    Tests can call ``create_app()`` with explicit settings instead of
    mutating process-wide environment.
    """
    resolved = settings or get_settings()
    application = FastAPI(
        title=resolved.app_name,
        version="0.1.0",
        description="AEGIS bootstrap foundation",
        debug=resolved.debug,
    )
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
