"""EventBridge publisher unit tests (no LocalStack)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from aegis.config.settings import Settings
from aegis.core.events import EVENT_SOURCE, incident_opened_v1
from aegis.core.protocols import EventPublisher
from aegis.infrastructure.messaging.publisher import EventBridgePublisher, build_event_publisher


def test_publish_puts_one_eventbridge_entry() -> None:
    client = MagicMock()
    client.put_events.return_value = {"FailedEntryCount": 0, "Entries": [{}]}
    publisher: EventPublisher = EventBridgePublisher(client=client, bus_name="aegis-events")
    event = incident_opened_v1(incident_id="inc-1", correlation_id="corr-1", event_id="evt-1")

    publisher.publish(event)

    entry = client.put_events.call_args.kwargs["Entries"][0]
    assert entry["Source"] == EVENT_SOURCE
    assert entry["DetailType"] == event.event_type
    assert entry["EventBusName"] == "aegis-events"
    detail = json.loads(entry["Detail"])
    assert detail["incident_id"] == "inc-1"
    assert detail["correlation_id"] == "corr-1"


def test_publish_raises_when_eventbridge_rejects_entry() -> None:
    client = MagicMock()
    client.put_events.return_value = {
        "FailedEntryCount": 1,
        "Entries": [{"ErrorCode": "InternalException"}],
    }
    publisher = EventBridgePublisher(client=client, bus_name="aegis-events")

    with pytest.raises(ConnectionError, match="PutEvents failed"):
        publisher.publish(incident_opened_v1(incident_id="inc-1", correlation_id="c"))


def test_build_event_publisher_none_when_endpoint_unset() -> None:
    settings = Settings(aws_endpoint="")
    assert build_event_publisher(settings) is None
