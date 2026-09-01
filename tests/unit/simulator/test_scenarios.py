"""Named failure scenarios bias signals without real faults (FR-082, FR-083)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.simulator.config import Settings
from apps.simulator.main import create_app
from apps.simulator.scenarios import (
    LATENCY_SPIKE_MS,
    SCENARIOS,
    ScenarioEngine,
    ScenarioId,
    scenario_catalog,
)
from apps.simulator.services import ServiceId, ServiceRuntime, ServiceStatus
from apps.simulator.signals import emit_healthy_tick
from apps.simulator.signals.emitter import HEALTHY_LATENCY_MS
from apps.simulator.signals.models import HealthyTick, LogSeverity

_FR083_IDS = (
    ScenarioId.DB_EXHAUSTION,
    ScenarioId.MEMORY_LEAK,
    ScenarioId.LATENCY_SPIKE,
    ScenarioId.BAD_DEPLOYMENT,
    ScenarioId.QUEUE_BACKLOG,
    ScenarioId.DEPENDENCY_FAILURE,
)
_CAP_MEMORY_BYTES = 256.0 + 20 * 64.0


def _emit(engine: ScenarioEngine, service: ServiceId) -> HealthyTick:
    return emit_healthy_tick(service, bias=engine.bias_for(service))


def _extra(tick: HealthyTick, name: str) -> float:
    match = [sample for sample in tick.extra_metrics if sample.name == name]
    assert len(match) == 1, f"expected one {name} metric, got {tick.extra_metrics!r}"
    return match[0].value


def test_all_fr083_ids_exist_in_the_catalog() -> None:
    assert tuple(item.id for item in scenario_catalog()) == _FR083_IDS
    assert set(SCENARIOS) == set(_FR083_IDS)
    assert {item.value for item in ScenarioId} == {
        "db_exhaustion",
        "memory_leak",
        "latency_spike",
        "bad_deployment",
        "queue_backlog",
        "dependency_failure",
    }


def test_latency_spike_increases_payment_latency_vs_healthy_baseline() -> None:
    healthy = emit_healthy_tick(ServiceId.PAYMENT)
    engine = ScenarioEngine()
    engine.activate(ScenarioId.LATENCY_SPIKE, ServiceRuntime())
    failing = _emit(engine, ServiceId.PAYMENT)

    assert healthy.metric.value == HEALTHY_LATENCY_MS
    assert failing.metric.value == LATENCY_SPIKE_MS
    assert failing.span.duration_ms == LATENCY_SPIKE_MS
    assert failing.metric.value > healthy.metric.value
    assert failing.log.severity is LogSeverity.WARNING
    assert failing.log.message == "slow request"

    untouched = _emit(engine, ServiceId.USER)
    assert untouched.metric.value == HEALTHY_LATENCY_MS
    assert untouched.log.message == "request completed"


def test_db_exhaustion_biases_payment_and_order() -> None:
    engine = ScenarioEngine()
    runtime = ServiceRuntime()
    engine.activate(ScenarioId.DB_EXHAUSTION, runtime)

    payment = _emit(engine, ServiceId.PAYMENT)
    order = _emit(engine, ServiceId.ORDER)
    inventory = _emit(engine, ServiceId.INVENTORY)

    assert runtime.status_of(ServiceId.PAYMENT) is ServiceStatus.DEGRADED
    assert runtime.status_of(ServiceId.ORDER) is ServiceStatus.DEGRADED
    assert payment.log.message == "too many connections"
    assert payment.log.severity is LogSeverity.ERROR
    assert _extra(payment, "error_rate") == 0.42
    assert order.log.message == "too many connections"
    assert inventory.metric.value == HEALTHY_LATENCY_MS


def test_memory_leak_grows_then_caps_the_gauge() -> None:
    engine = ScenarioEngine()
    engine.activate(ScenarioId.MEMORY_LEAK, ServiceRuntime())

    first = _emit(engine, ServiceId.USER)
    second = _emit(engine, ServiceId.USER)
    assert first.log.message == "GC thrash; approaching OOM"
    assert first.log.severity is LogSeverity.WARNING
    assert _extra(second, "memory_bytes") > _extra(first, "memory_bytes")

    last = first
    for _ in range(23):
        last = _emit(engine, ServiceId.USER)
    assert _extra(last, "memory_bytes") == _CAP_MEMORY_BYTES
    assert _extra(_emit(engine, ServiceId.USER), "memory_bytes") == _CAP_MEMORY_BYTES


def test_bad_deployment_emits_version_bump_and_5xx_logs() -> None:
    engine = ScenarioEngine()
    runtime = ServiceRuntime()
    engine.activate(ScenarioId.BAD_DEPLOYMENT, runtime)
    tick = _emit(engine, ServiceId.USER)

    assert runtime.status_of(ServiceId.USER) is ServiceStatus.DOWN
    assert tick.log.severity is LogSeverity.ERROR
    assert "5xx" in tick.log.message
    assert tick.deployment is not None
    assert tick.deployment.version == "2026.9.1-bad"
    assert _extra(tick, "error_rate") == 0.55


def test_queue_backlog_raises_notification_depth() -> None:
    engine = ScenarioEngine()
    engine.activate(ScenarioId.QUEUE_BACKLOG, ServiceRuntime())
    tick = _emit(engine, ServiceId.NOTIFICATION)

    assert tick.log.message == "consumer lag increasing"
    assert _extra(tick, "queue_depth") == 1200.0


def test_dependency_failure_times_out_calling_downstream() -> None:
    engine = ScenarioEngine()
    engine.activate(ScenarioId.DEPENDENCY_FAILURE, ServiceRuntime())
    first = _emit(engine, ServiceId.ORDER)
    second = _emit(engine, ServiceId.ORDER)

    assert first.log.message == "timeout calling payment"
    assert second.log.message == "timeout calling inventory"
    assert first.metric.value == HEALTHY_LATENCY_MS * 8
    assert _extra(first, "error_rate") == 0.31


def test_activating_a_second_scenario_replaces_the_first() -> None:
    engine = ScenarioEngine()
    runtime = ServiceRuntime()
    engine.activate(ScenarioId.LATENCY_SPIKE, runtime)
    engine.activate(ScenarioId.QUEUE_BACKLOG, runtime)

    assert engine.active_id is ScenarioId.QUEUE_BACKLOG
    assert runtime.status_of(ServiceId.PAYMENT) is ServiceStatus.HEALTHY
    assert runtime.status_of(ServiceId.NOTIFICATION) is ServiceStatus.DEGRADED
    assert _emit(engine, ServiceId.PAYMENT).metric.value == HEALTHY_LATENCY_MS
    assert _extra(_emit(engine, ServiceId.NOTIFICATION), "queue_depth") == 1200.0


def test_deactivate_returns_all_services_to_healthy() -> None:
    engine = ScenarioEngine()
    runtime = ServiceRuntime()
    engine.activate(ScenarioId.DB_EXHAUSTION, runtime)
    engine.deactivate(runtime)

    assert engine.active_id is None
    assert all(row.status is ServiceStatus.HEALTHY for row in runtime.list_snapshots())
    assert _emit(engine, ServiceId.PAYMENT).metric.value == HEALTHY_LATENCY_MS


def test_get_scenarios_lists_ids_and_active_flag() -> None:
    application = create_app(Settings(environment="test"))
    with TestClient(application) as client:
        listed = client.get("/scenarios")
        activated = client.post("/scenarios/latency_spike")
        services = client.get("/services")
        tick = client.post("/signals/tick", params={"service": "payment"})
        cleared = client.delete("/scenarios")

    assert listed.status_code == 200
    assert listed.json()["active"] is None
    assert [item["id"] for item in listed.json()["items"]] == [item.value for item in _FR083_IDS]
    assert all(item["active"] is False for item in listed.json()["items"])

    assert activated.status_code == 200
    assert activated.json()["active"] == "latency_spike"
    active_row = next(item for item in activated.json()["items"] if item["id"] == "latency_spike")
    assert active_row["active"] is True
    assert active_row["affected"] == ["payment"]

    payment = next(item for item in services.json() if item["id"] == "payment")
    assert payment["status"] == "degraded"

    latency = next(item for item in tick.json()["items"] if item.get("name") == "latency_ms")
    assert latency["value"] == LATENCY_SPIKE_MS
    span = next(item for item in tick.json()["items"] if item["kind"] == "span")
    assert span["duration_ms"] == LATENCY_SPIKE_MS

    assert cleared.status_code == 200
    assert cleared.json()["active"] is None


def test_boot_config_activates_one_scenario() -> None:
    application = create_app(
        Settings(environment="test", scenario=ScenarioId.QUEUE_BACKLOG),
    )
    with TestClient(application) as client:
        listed = client.get("/scenarios")
        tick = client.post("/signals/tick", params={"service": "notification"})

    assert listed.json()["active"] == "queue_backlog"
    depth = next(item for item in tick.json()["items"] if item.get("name") == "queue_depth")
    assert depth["value"] == 1200.0


def test_unknown_scenario_id_is_rejected() -> None:
    application = create_app(Settings(environment="test"))
    with TestClient(application) as client:
        response = client.post("/scenarios/fork_bomb")

    assert response.status_code == 422


def test_http_ticks_do_not_call_aegis() -> None:
    application = create_app(Settings(environment="test", aegis_base_url="http://127.0.0.1:8000"))
    with TestClient(application) as client:
        client.post("/scenarios/bad_deployment")
        response = client.post("/signals/tick", params={"service": "user"})

    kinds = [item["kind"] for item in response.json()["items"]]
    assert "deployment" in kinds
    assert "aegis" not in str(response.json()).lower()
