"""Configurable failure scenarios (FR-082, FR-083)."""

from apps.simulator.scenarios.catalog import (
    SCENARIOS,
    ScenarioId,
    ScenarioSpec,
    scenario_catalog,
)
from apps.simulator.scenarios.engine import LATENCY_SPIKE_MS, ScenarioEngine

__all__ = [
    "LATENCY_SPIKE_MS",
    "SCENARIOS",
    "ScenarioEngine",
    "ScenarioId",
    "ScenarioSpec",
    "scenario_catalog",
]
