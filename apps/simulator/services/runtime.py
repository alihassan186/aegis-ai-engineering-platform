"""In-memory service health. Status is data, not real resource pressure."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apps.simulator.services.catalog import SERVICES, ServiceId, ServiceSpec, catalog


class ServiceStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass(frozen=True, slots=True)
class ServiceSnapshot:
    """One catalog spec plus in-memory status (healthy, degraded, or down)."""

    spec: ServiceSpec
    status: ServiceStatus


class ServiceRuntime:
    """One status per catalog service. Defaults to healthy."""

    def __init__(self) -> None:
        self._status: dict[ServiceId, ServiceStatus] = {
            service_id: ServiceStatus.HEALTHY for service_id in SERVICES
        }

    def list_snapshots(self) -> tuple[ServiceSnapshot, ...]:
        return tuple(ServiceSnapshot(spec=spec, status=self._status[spec.id]) for spec in catalog())

    def status_of(self, service_id: ServiceId) -> ServiceStatus:
        return self._status[service_id]

    def set_status(self, service_id: ServiceId, status: ServiceStatus) -> None:
        if service_id not in SERVICES:
            raise KeyError(service_id)
        self._status[service_id] = status
