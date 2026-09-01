"""Healthy synthetic signals for one service (FR-081)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from apps.simulator.config import Settings
from apps.simulator.main import create_app
from apps.simulator.services import ServiceId, catalog
from apps.simulator.signals import SignalBuffer, emit_healthy_tick
from apps.simulator.signals.emitter import HEALTHY_LATENCY_MS
from apps.simulator.signals.models import LogSeverity

_FIXED_NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
_IDS = iter(["trace-payment", "span-payment"])


def _clock() -> datetime:
    return _FIXED_NOW


def _ids() -> str:
    return next(_IDS)


def test_emit_payment_includes_log_metric_and_span() -> None:
    tick = emit_healthy_tick(ServiceId.PAYMENT, clock=_clock, new_id=_ids)

    assert tick.log.service is ServiceId.PAYMENT
    assert tick.log.severity is LogSeverity.INFO
    assert tick.log.message == "request completed"
    assert tick.log.timestamp == _FIXED_NOW
    assert tick.log.trace_id == "trace-payment"

    assert tick.metric.name == "latency_ms"
    assert tick.metric.value == HEALTHY_LATENCY_MS
    assert tick.metric.unit == "ms"
    assert tick.metric.trace_id == "trace-payment"

    assert tick.span.service is ServiceId.PAYMENT
    assert tick.span.trace_id == "trace-payment"
    assert tick.span.span_id == "span-payment"
    assert tick.span.duration_ms == HEALTHY_LATENCY_MS


def test_all_five_services_emit_the_three_signal_types() -> None:
    for spec in catalog():
        tick = emit_healthy_tick(spec.id, clock=_clock)
        assert tick.log.service is spec.id
        assert tick.metric.service is spec.id
        assert tick.span.service is spec.id
        assert tick.log.trace_id == tick.metric.trace_id == tick.span.trace_id


def test_buffer_filters_recent_ticks_by_service() -> None:
    buffer = SignalBuffer()
    buffer.emit_healthy(ServiceId.USER, clock=_clock)
    buffer.emit_healthy(ServiceId.PAYMENT, clock=_clock)

    payment_only = buffer.recent(service=ServiceId.PAYMENT)
    assert len(payment_only) == 1
    assert payment_only[0].log.service is ServiceId.PAYMENT


def test_get_signals_for_payment_after_tick() -> None:
    application = create_app(Settings(environment="test"))
    with TestClient(application) as client:
        emitted = client.post("/signals/tick", params={"service": "payment"})
        listed = client.get("/signals", params={"service": "payment"})

    assert emitted.status_code == 200
    assert listed.status_code == 200
    kinds = [item["kind"] for item in listed.json()["items"]]
    assert kinds == ["log", "metric", "span"]
    assert all(item["service"] == "payment" for item in listed.json()["items"])
    log = listed.json()["items"][0]
    assert log["severity"] == "info"
    assert log["message"] == "request completed"
    metric = listed.json()["items"][1]
    assert metric["name"] == "latency_ms"
    span = listed.json()["items"][2]
    assert "span_id" in span
    assert span["duration_ms"] == HEALTHY_LATENCY_MS
