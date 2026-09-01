"""Simulator process entry (FR-080 skeleton).

Run separately from AEGIS::

    uv run uvicorn apps.simulator.main:app --host 127.0.0.1 --port 8001
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from apps.simulator.aegis_client import AegisClient, AegisUnreachableError, signal_from_scenario
from apps.simulator.config import Settings, get_settings
from apps.simulator.scenarios import SCENARIOS, ScenarioEngine, ScenarioId, scenario_catalog
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


class DeploymentSignalResponse(BaseModel):
    kind: str = "deployment"
    timestamp: datetime
    service: ServiceId
    version: str
    trace_id: str


class SignalsResponse(BaseModel):
    items: list[
        LogSignalResponse | MetricSignalResponse | SpanSignalResponse | DeploymentSignalResponse
    ]


class ScenarioItemResponse(BaseModel):
    id: ScenarioId
    display_name: str
    affected: list[ServiceId]
    active: bool


class ScenarioListResponse(BaseModel):
    active: ScenarioId | None
    items: list[ScenarioItemResponse]


def _signal_items(
    ticks: Sequence[HealthyTick],
) -> list[LogSignalResponse | MetricSignalResponse | SpanSignalResponse | DeploymentSignalResponse]:
    items: list[
        LogSignalResponse | MetricSignalResponse | SpanSignalResponse | DeploymentSignalResponse
    ] = []
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
        for extra in tick.extra_metrics:
            items.append(
                MetricSignalResponse(
                    timestamp=extra.timestamp,
                    service=extra.service,
                    name=extra.name,
                    value=extra.value,
                    unit=extra.unit,
                    trace_id=extra.trace_id,
                )
            )
        if tick.deployment is not None:
            items.append(
                DeploymentSignalResponse(
                    timestamp=tick.deployment.timestamp,
                    service=tick.deployment.service,
                    version=tick.deployment.version,
                    trace_id=tick.deployment.trace_id,
                )
            )
    return items


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        runtime = ServiceRuntime()
        engine = ScenarioEngine()
        if resolved.scenario is not None:
            engine.activate(resolved.scenario, runtime)
        application.state.boot_message = BOOT_MESSAGE
        application.state.runtime = runtime
        application.state.signals = SignalBuffer()
        application.state.scenarios = engine
        application.state.aegis_client = AegisClient(
            base_url=resolved.aegis_base_url,
            secret=resolved.webhook_secret,
        )
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
    def emit_signals(
        service: ServiceId = Query(..., description="Catalog service to emit one tick for"),
    ) -> SignalsResponse:
        buffer: SignalBuffer = application.state.signals
        engine: ScenarioEngine = application.state.scenarios
        tick = buffer.emit_healthy(service, bias=engine.bias_for(service))
        return SignalsResponse(items=_signal_items((tick,)))

    @application.get("/scenarios", response_model=ScenarioListResponse)
    def list_scenarios() -> ScenarioListResponse:
        engine: ScenarioEngine = application.state.scenarios
        active = engine.active_id
        return ScenarioListResponse(
            active=active,
            items=[
                ScenarioItemResponse(
                    id=spec.id,
                    display_name=spec.display_name,
                    affected=sorted(spec.affected),
                    active=active is spec.id,
                )
                for spec in scenario_catalog()
            ],
        )

    @application.post("/scenarios/{scenario_id}", response_model=ScenarioListResponse)
    def activate_scenario(scenario_id: ScenarioId) -> ScenarioListResponse:
        engine: ScenarioEngine = application.state.scenarios
        runtime: ServiceRuntime = application.state.runtime
        engine.activate(scenario_id, runtime)
        return list_scenarios()

    @application.delete("/scenarios", response_model=ScenarioListResponse)
    def deactivate_scenario() -> ScenarioListResponse:
        engine: ScenarioEngine = application.state.scenarios
        runtime: ServiceRuntime = application.state.runtime
        engine.deactivate(runtime)
        return list_scenarios()

    @application.post("/emit")
    def emit_incident_signal() -> JSONResponse:
        engine: ScenarioEngine = application.state.scenarios
        resolved_settings: Settings = application.state.settings
        if engine.active_id is None:
            return JSONResponse(
                status_code=409,
                content={
                    "error": {
                        "code": "NO_ACTIVE_SCENARIO",
                        "message": "Activate a scenario before emitting.",
                    }
                },
            )
        if not resolved_settings.aegis_base_url:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "AEGIS_NOT_CONFIGURED",
                        "message": "Set AEGIS_BASE_URL.",
                    }
                },
            )
        if not resolved_settings.webhook_secret:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "WEBHOOK_NOT_CONFIGURED",
                        "message": "Set SIMULATOR_WEBHOOK_SECRET.",
                    }
                },
            )
        client: AegisClient = application.state.aegis_client
        try:
            result = client.emit_incident_signal(signal_from_scenario(SCENARIOS[engine.active_id]))
        except AegisUnreachableError as exc:
            return JSONResponse(
                status_code=502,
                content={"error": {"code": "AEGIS_UNREACHABLE", "message": str(exc)}},
            )
        try:
            payload = json.loads(result.body.decode("utf-8")) if result.body else {}
        except json.JSONDecodeError:
            payload = {"raw": result.body.decode("utf-8", errors="replace")}
        return JSONResponse(status_code=result.status_code, content=payload)

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
