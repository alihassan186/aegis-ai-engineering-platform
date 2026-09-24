"""Versioned HTTP API."""

from fastapi import APIRouter

from aegis.api.incidents.router import router as incidents_router
from aegis.api.investigations.router import router as investigations_router
from aegis.api.rag.router import router as rag_router
from aegis.api.reports.router import router as reports_router
from aegis.api.webhooks.router import router as webhooks_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(incidents_router, prefix="/incidents", tags=["incidents"])
api_v1_router.include_router(
    investigations_router,
    prefix="/incidents/{id}/investigation",
    tags=["investigations"],
)
api_v1_router.include_router(
    reports_router,
    prefix="/incidents/{id}/report",
    tags=["reports"],
)
api_v1_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
api_v1_router.include_router(rag_router, tags=["rag"])
