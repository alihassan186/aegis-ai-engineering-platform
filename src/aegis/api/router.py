"""Versioned HTTP API."""

from fastapi import APIRouter

from aegis.api.incidents.router import router as incidents_router
from aegis.api.webhooks.router import router as webhooks_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(incidents_router, prefix="/incidents", tags=["incidents"])
api_v1_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
