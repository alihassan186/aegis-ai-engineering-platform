"""Live LocalStack EventBridge → SQS (Step 4.1). Skips without AEGIS_AWS_ENDPOINT."""

from __future__ import annotations

import os

import pytest

from aegis.config.settings import Settings
from aegis.core.events import INCIDENT_OPENED_V1, incident_opened_v1
from aegis.infrastructure.messaging.provision import ensure_investigation_topology
from aegis.infrastructure.messaging.publisher import EventBridgePublisher, build_event_publisher
from aegis.infrastructure.messaging.sqs import (
    delete_message,
    domain_event_from_sqs_body,
    receive_one,
)


@pytest.fixture
def settings() -> Settings:
    endpoint = os.getenv("AEGIS_AWS_ENDPOINT", "").strip().rstrip("/")
    if not endpoint:
        pytest.skip("AEGIS_AWS_ENDPOINT is unset; LocalStack is optional for this suite.")
    return Settings(
        aws_endpoint=endpoint,
        aws_region=os.getenv("AEGIS_AWS_REGION", "").strip() or "eu-west-1",
        event_bus_name="aegis-events",
        investigation_queue_name="investigation-workflow",
    )


@pytest.mark.integration
def test_publish_incident_opened_is_received_on_investigation_queue(settings: Settings) -> None:
    topology = ensure_investigation_topology(settings)
    assert topology.bus_name == "aegis-events"
    assert topology.queue_name == "investigation-workflow"
    assert topology.dlq_name == "investigation-workflow-dlq"

    publisher = build_event_publisher(settings)
    assert isinstance(publisher, EventBridgePublisher)

    event = incident_opened_v1(
        incident_id="22222222-2222-2222-2222-222222222222",
        correlation_id="req-4-1",
        event_id="evt-4-1",
    )
    publisher.publish(event)

    message = receive_one(settings, wait_seconds=20)
    assert message is not None
    parsed = domain_event_from_sqs_body(message["Body"])
    assert parsed.event_type == INCIDENT_OPENED_V1
    assert parsed.incident_id == event.incident_id
    assert parsed.correlation_id == event.correlation_id
    assert parsed.event_id == event.event_id
    delete_message(settings, message["ReceiptHandle"])
