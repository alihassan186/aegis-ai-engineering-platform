"""Map an active scenario to service status and signal bias (FR-082, FR-083)."""

from __future__ import annotations

from dataclasses import dataclass

from apps.simulator.scenarios.catalog import SCENARIOS, ScenarioId, ScenarioSpec
from apps.simulator.services.catalog import SERVICES, ServiceId
from apps.simulator.services.runtime import ServiceRuntime, ServiceStatus
from apps.simulator.signals.emitter import HEALTHY_LATENCY_MS, SignalBias
from apps.simulator.signals.models import LogSeverity

LATENCY_SPIKE_MS = 850.0
_MAX_LEAK_STEPS = 20
_MEMORY_STEP_BYTES = 64.0
_BASE_MEMORY_BYTES = 256.0


@dataclass(frozen=True, slots=True)
class ScenarioState:
    spec: ScenarioSpec | None
    tick_index: int


class ScenarioEngine:
    """At most one active scenario. Bias is numbers and log text, not real faults."""

    def __init__(self) -> None:
        self._active: ScenarioSpec | None = None
        self._tick_index = 0

    @property
    def active_id(self) -> ScenarioId | None:
        return None if self._active is None else self._active.id

    def snapshot(self) -> ScenarioState:
        return ScenarioState(spec=self._active, tick_index=self._tick_index)

    def activate(self, scenario_id: ScenarioId, runtime: ServiceRuntime) -> ScenarioSpec:
        spec = SCENARIOS[scenario_id]
        self._reset_runtime(runtime)
        for service_id, status in spec.statuses.items():
            runtime.set_status(service_id, status)
        self._active = spec
        self._tick_index = 0
        return spec

    def deactivate(self, runtime: ServiceRuntime) -> None:
        self._active = None
        self._tick_index = 0
        self._reset_runtime(runtime)

    def bias_for(self, service: ServiceId) -> SignalBias:
        spec = self._active
        if spec is None or service not in spec.affected:
            return SignalBias()
        self._tick_index += 1
        return _bias(spec.id, self._tick_index)

    def _reset_runtime(self, runtime: ServiceRuntime) -> None:
        for service_id in SERVICES:
            runtime.set_status(service_id, ServiceStatus.HEALTHY)


def _bias(scenario_id: ScenarioId, tick_index: int) -> SignalBias:
    if scenario_id is ScenarioId.DB_EXHAUSTION:
        return SignalBias(
            log_severity=LogSeverity.ERROR,
            log_message="too many connections",
            latency_ms=HEALTHY_LATENCY_MS * 4,
            extra_metric_name="error_rate",
            extra_metric_value=0.42,
            extra_metric_unit="ratio",
        )
    if scenario_id is ScenarioId.MEMORY_LEAK:
        steps = min(tick_index, _MAX_LEAK_STEPS)
        return SignalBias(
            log_severity=LogSeverity.WARNING,
            log_message="GC thrash; approaching OOM",
            extra_metric_name="memory_bytes",
            extra_metric_value=_BASE_MEMORY_BYTES + steps * _MEMORY_STEP_BYTES,
            extra_metric_unit="bytes",
        )
    if scenario_id is ScenarioId.LATENCY_SPIKE:
        return SignalBias(
            log_severity=LogSeverity.WARNING,
            log_message="slow request",
            latency_ms=LATENCY_SPIKE_MS,
        )
    if scenario_id is ScenarioId.BAD_DEPLOYMENT:
        return SignalBias(
            log_severity=LogSeverity.ERROR,
            log_message="upstream returned 5xx after version bump",
            latency_ms=HEALTHY_LATENCY_MS * 2,
            extra_metric_name="error_rate",
            extra_metric_value=0.55,
            extra_metric_unit="ratio",
            deploy_version="2026.9.1-bad",
        )
    if scenario_id is ScenarioId.QUEUE_BACKLOG:
        return SignalBias(
            log_severity=LogSeverity.WARNING,
            log_message="consumer lag increasing",
            extra_metric_name="queue_depth",
            extra_metric_value=1200.0,
            extra_metric_unit="1",
        )
    if scenario_id is ScenarioId.DEPENDENCY_FAILURE:
        target = "payment" if tick_index % 2 == 1 else "inventory"
        return SignalBias(
            log_severity=LogSeverity.ERROR,
            log_message=f"timeout calling {target}",
            latency_ms=HEALTHY_LATENCY_MS * 8,
            extra_metric_name="error_rate",
            extra_metric_value=0.31,
            extra_metric_unit="ratio",
        )
    return SignalBias()
