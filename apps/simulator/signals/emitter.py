"""Emit a healthy tick for one service at a given clock time (FR-081)."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from uuid import uuid4

from apps.simulator.services.catalog import SERVICES, ServiceId
from apps.simulator.signals.models import (
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


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def emit_healthy_tick(
    service: ServiceId,
    *,
    clock: Clock | None = None,
    new_id: IdFactory | None = None,
    latency_ms: float = HEALTHY_LATENCY_MS,
) -> HealthyTick:
    """One INFO log, one latency metric, one span. Failure modes are Step 2.4."""
    if service not in SERVICES:
        raise KeyError(service)
    moment = (clock or utc_now)()
    make_id = new_id or (lambda: uuid4().hex)
    trace_id = make_id()
    span_id = make_id()
    return HealthyTick(
        log=LogRecord(
            timestamp=moment,
            service=service,
            severity=LogSeverity.INFO,
            message="request completed",
            trace_id=trace_id,
        ),
        metric=MetricSample(
            timestamp=moment,
            service=service,
            name="latency_ms",
            value=latency_ms,
            unit="ms",
            trace_id=trace_id,
        ),
        span=TraceSpan(
            timestamp=moment,
            service=service,
            trace_id=trace_id,
            span_id=span_id,
            duration_ms=latency_ms,
        ),
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
    ) -> HealthyTick:
        tick = emit_healthy_tick(service, clock=clock, new_id=new_id)
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
