"""Simulator process entry (FR-080 skeleton).

Run separately from AEGIS::

    uv run uvicorn apps.simulator.main:app --host 127.0.0.1 --port 8001
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Query
from pydantic import BaseModel

from apps.simulator.config import Settings, get_settings
from apps.simulator.services import ServiceId, ServiceRuntime, ServiceStatus
from apps.simulator.signals import HealthyTick, SignalBuffer

BOOT_MESSAGE = "simulator boot"


class ServiceResponse(BaseModel):
    id: ServiceId
    display_name: str
    depends_on: list[ServiceId]
    status: ServiceStatus


class LogSignalResponse(BaseModel):
    kind: str = "log"
    timestamp: datetime
    service: ServiceId
    severity: str
    message: str
    trace_id: str


class MetricSignalResponse(BaseModel):
    kind: str = "metric"
    timestamp: datetime
    service: ServiceId
    name: str
    value: float
    unit: str
    trace_id: str


class SpanSignalResponse(BaseModel):
    kind: str = "span"
    timestamp: datetime
    service: ServiceId
    trace_id: str
    span_id: str
    duration_ms: float


class SignalsResponse(BaseModel):
    items: list[LogSignalResponse | MetricSignalResponse | SpanSignalResponse]


def _signal_items(
    ticks: Sequence[HealthyTick],
) -> list[LogSignalResponse | MetricSignalResponse | SpanSignalResponse]:
    items: list[LogSignalResponse | MetricSignalResponse | SpanSignalResponse] = []
    for tick in ticks:
        items.append(
            LogSignalResponse(
                timestamp=tick.log.timestamp,
                service=tick.log.service,
                severity=tick.log.severity.value,
                message=tick.log.message,
                trace_id=tick.log.trace_id,
            )
        )
        items.append(
            MetricSignalResponse(
                timestamp=tick.metric.timestamp,
                service=tick.metric.service,
                name=tick.metric.name,
                value=tick.metric.value,
                unit=tick.metric.unit,
                trace_id=tick.metric.trace_id,
            )
        )
        items.append(
            SpanSignalResponse(
                timestamp=tick.span.timestamp,
                service=tick.span.service,
                trace_id=tick.span.trace_id,
                span_id=tick.span.span_id,
                duration_ms=tick.span.duration_ms,
            )
        )
    return items


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.boot_message = BOOT_MESSAGE
        application.state.runtime = ServiceRuntime()
        application.state.signals = SignalBuffer()
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

    @application.post("/signals/tick", response_model=SignalsResponse)
    def emit_healthy_signals(
        service: ServiceId = Query(..., description="Catalog service to emit a healthy tick for"),
    ) -> SignalsResponse:
        buffer: SignalBuffer = application.state.signals
        tick = buffer.emit_healthy(service)
        return SignalsResponse(items=_signal_items((tick,)))

    @application.get("/signals", response_model=SignalsResponse)
    def list_signals(
        service: ServiceId | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=256),
    ) -> SignalsResponse:
        buffer: SignalBuffer = application.state.signals
        ticks = buffer.recent(service=service, limit=limit)
        return SignalsResponse(items=_signal_items(ticks))

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
