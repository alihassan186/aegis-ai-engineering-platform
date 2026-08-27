"""Minimal FastAPI application entry point for the AEGIS bootstrap."""

from __future__ import annotations

from fastapi import FastAPI

from aegis.config.settings import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AEGIS bootstrap foundation",
    debug=settings.debug,
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("aegis.main:app", host="127.0.0.1", port=8000, reload=settings.debug)
