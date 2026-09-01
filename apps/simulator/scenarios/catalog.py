"""FR-083 failure scenarios as named config (not real resource faults)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from apps.simulator.services.catalog import ServiceId
from apps.simulator.services.runtime import ServiceStatus


class ScenarioId(StrEnum):
    DB_EXHAUSTION = "db_exhaustion"
    MEMORY_LEAK = "memory_leak"
    LATENCY_SPIKE = "latency_spike"
    BAD_DEPLOYMENT = "bad_deployment"
    QUEUE_BACKLOG = "queue_backlog"
    DEPENDENCY_FAILURE = "dependency_failure"


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    id: ScenarioId
    display_name: str
    affected: frozenset[ServiceId]
    statuses: Mapping[ServiceId, ServiceStatus]


SCENARIOS: Mapping[ScenarioId, ScenarioSpec] = {
    ScenarioId.DB_EXHAUSTION: ScenarioSpec(
        id=ScenarioId.DB_EXHAUSTION,
        display_name="DB connection exhaustion",
        affected=frozenset({ServiceId.PAYMENT, ServiceId.ORDER}),
        statuses={
            ServiceId.PAYMENT: ServiceStatus.DEGRADED,
            ServiceId.ORDER: ServiceStatus.DEGRADED,
        },
    ),
    ScenarioId.MEMORY_LEAK: ScenarioSpec(
        id=ScenarioId.MEMORY_LEAK,
        display_name="Memory leak",
        affected=frozenset({ServiceId.USER}),
        statuses={ServiceId.USER: ServiceStatus.DEGRADED},
    ),
    ScenarioId.LATENCY_SPIKE: ScenarioSpec(
        id=ScenarioId.LATENCY_SPIKE,
        display_name="Latency spike",
        affected=frozenset({ServiceId.PAYMENT}),
        statuses={ServiceId.PAYMENT: ServiceStatus.DEGRADED},
    ),
    ScenarioId.BAD_DEPLOYMENT: ScenarioSpec(
        id=ScenarioId.BAD_DEPLOYMENT,
        display_name="Bad deployment",
        affected=frozenset({ServiceId.USER}),
        statuses={ServiceId.USER: ServiceStatus.DOWN},
    ),
    ScenarioId.QUEUE_BACKLOG: ScenarioSpec(
        id=ScenarioId.QUEUE_BACKLOG,
        display_name="Queue backlog",
        affected=frozenset({ServiceId.NOTIFICATION}),
        statuses={ServiceId.NOTIFICATION: ServiceStatus.DEGRADED},
    ),
    ScenarioId.DEPENDENCY_FAILURE: ScenarioSpec(
        id=ScenarioId.DEPENDENCY_FAILURE,
        display_name="Dependency failure",
        affected=frozenset({ServiceId.ORDER}),
        statuses={ServiceId.ORDER: ServiceStatus.DEGRADED},
    ),
}


def scenario_catalog() -> tuple[ScenarioSpec, ...]:
    return (
        SCENARIOS[ScenarioId.DB_EXHAUSTION],
        SCENARIOS[ScenarioId.MEMORY_LEAK],
        SCENARIOS[ScenarioId.LATENCY_SPIKE],
        SCENARIOS[ScenarioId.BAD_DEPLOYMENT],
        SCENARIOS[ScenarioId.QUEUE_BACKLOG],
        SCENARIOS[ScenarioId.DEPENDENCY_FAILURE],
    )
