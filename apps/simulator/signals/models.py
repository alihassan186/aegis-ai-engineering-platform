"""Synthetic observability records (FR-081). Not a vendor telemetry SDK."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apps.simulator.services.catalog import ServiceId


class LogSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class LogRecord:
    timestamp: datetime
    service: ServiceId
    severity: LogSeverity
    message: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class MetricSample:
    timestamp: datetime
    service: ServiceId
    name: str
    value: float
    unit: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class TraceSpan:
    timestamp: datetime
    service: ServiceId
    trace_id: str
    span_id: str
    duration_ms: float


@dataclass(frozen=True, slots=True)
class DeploymentEvent:
    """Optional §13 signal. Not a CI system — just a version bump record."""

    timestamp: datetime
    service: ServiceId
    version: str
    trace_id: str


@dataclass(frozen=True, slots=True)
class HealthyTick:
    log: LogRecord
    metric: MetricSample
    span: TraceSpan
