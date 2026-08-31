"""Synthetic multi-service catalog (FR-080)."""

from apps.simulator.services.catalog import SERVICES, ServiceId, ServiceSpec, catalog
from apps.simulator.services.runtime import ServiceRuntime, ServiceSnapshot, ServiceStatus

__all__ = [
    "SERVICES",
    "ServiceId",
    "ServiceRuntime",
    "ServiceSnapshot",
    "ServiceSpec",
    "ServiceStatus",
    "catalog",
]
