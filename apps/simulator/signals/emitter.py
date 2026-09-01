"""Emit a tick for one service at a given clock time (FR-081, FR-082)."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from apps.simulator.services.catalog import SERVICES, ServiceId
from apps.simulator.signals.models import (
    DeploymentEvent,
    HealthyTick,
    LogRecord,
    LogSeverity,
    MetricSample,
    TraceSpan,
)

HEALTHY_LATENCY_MS = 12.0
_DEFAULT_BUFFER_SIZE = 256

Clock = Callable[[], datetime]
IdFactory = Callable[[], str]


@dataclass(frozen=True, slots=True)
class SignalBias:
    """Numbers and log text only. Never allocates unbounded structures."""

    log_severity: LogSeverity = LogSeverity.INFO
    log_message: str = "request completed"
    latency_ms: float = HEALTHY_LATENCY_MS
    extra_metric_name: str | None = None
    extra_metric_value: float | None = None
    extra_metric_unit: str = "1"
    deploy_version: str | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def emit_healthy_tick(
    service: ServiceId,
    *,
    clock: Clock | None = None,
    new_id: IdFactory | None = None,
    latency_ms: float = HEALTHY_LATENCY_MS,
    bias: SignalBias | None = None,
) -> HealthyTick:
    """One log, one latency metric, one span. Optional scenario bias (Step 2.4)."""
    if service not in SERVICES:
        raise KeyError(service)
    resolved = bias if bias is not None else SignalBias(latency_ms=latency_ms)
    moment = (clock or utc_now)()
    make_id = new_id or (lambda: uuid4().hex)
    trace_id = make_id()
    span_id = make_id()
    extra: tuple[MetricSample, ...] = ()
    if resolved.extra_metric_name is not None and resolved.extra_metric_value is not None:
        extra = (
            MetricSample(
                timestamp=moment,
                service=service,
                name=resolved.extra_metric_name,
                value=resolved.extra_metric_value,
                unit=resolved.extra_metric_unit,
                trace_id=trace_id,
            ),
        )
    deployment = None
    if resolved.deploy_version is not None:
        deployment = DeploymentEvent(
            timestamp=moment,
            service=service,
            version=resolved.deploy_version,
            trace_id=trace_id,
        )
    return HealthyTick(
        log=LogRecord(
            timestamp=moment,
            service=service,
            severity=resolved.log_severity,
            message=resolved.log_message,
            trace_id=trace_id,
        ),
        metric=MetricSample(
            timestamp=moment,
            service=service,
            name="latency_ms",
            value=resolved.latency_ms,
            unit="ms",
            trace_id=trace_id,
        ),
        span=TraceSpan(
            timestamp=moment,
            service=service,
            trace_id=trace_id,
            span_id=span_id,
            duration_ms=resolved.latency_ms,
        ),
        extra_metrics=extra,
        deployment=deployment,
    )


class SignalBuffer:
    """In-memory ring buffer. AEGIS Postgres is not a telemetry store."""

    def __init__(self, *, maxlen: int = _DEFAULT_BUFFER_SIZE) -> None:
        self._ticks: deque[HealthyTick] = deque(maxlen=maxlen)

    def append(self, tick: HealthyTick) -> None:
        self._ticks.append(tick)

    def emit_healthy(
        self,
        service: ServiceId,
        *,
        clock: Clock | None = None,
        new_id: IdFactory | None = None,
        bias: SignalBias | None = None,
    ) -> HealthyTick:
        tick = emit_healthy_tick(service, clock=clock, new_id=new_id, bias=bias)
        self.append(tick)
        return tick

    def recent(
        self,
        *,
        service: ServiceId | None = None,
        limit: int = 50,
    ) -> tuple[HealthyTick, ...]:
        items: Sequence[HealthyTick] = tuple(self._ticks)
        if service is not None:
            items = tuple(tick for tick in items if tick.log.service is service)
        if limit < 1:
            return ()
        return tuple(items[-limit:])
