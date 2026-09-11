"""SQS body unwrap (EventBridge wrap). No network."""

from __future__ import annotations

import json

from aegis.core.events import INCIDENT_OPENED_V1, incident_opened_v1
from aegis.infrastructure.messaging.sqs import domain_event_from_sqs_body


def test_unwraps_eventbridge_detail_object() -> None:
    event = incident_opened_v1(
        incident_id="inc-1",
        correlation_id="corr-1",
        event_id="evt-1",
    )
    body = json.dumps(
        {
            "source": "aegis.incidents",
            "detail-type": INCIDENT_OPENED_V1,
            "detail": event.as_detail(),
        }
    )
    parsed = domain_event_from_sqs_body(body)
    assert parsed.event_id == "evt-1"
    assert parsed.incident_id == "inc-1"
    assert parsed.event_type == INCIDENT_OPENED_V1


def test_unwraps_eventbridge_detail_json_string() -> None:
    event = incident_opened_v1(
        incident_id="inc-2",
        correlation_id="corr-2",
        event_id="evt-2",
    )
    body = json.dumps({"detail": json.dumps(event.as_detail())})
    parsed = domain_event_from_sqs_body(body)
    assert parsed.correlation_id == "corr-2"
    assert parsed.incident_id == "inc-2"
