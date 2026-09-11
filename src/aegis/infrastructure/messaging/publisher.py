"""EventBridge PutEvents adapter. No FastAPI, no LangGraph."""

from __future__ import annotations

import json
from typing import Any

from aegis.config.settings import Settings
from aegis.core.events import EVENT_SOURCE, DomainEvent
from aegis.infrastructure.messaging.clients import boto3_client
from aegis.infrastructure.messaging.names import EVENT_BUS_NAME


class EventBridgePublisher:
    """``EventPublisher`` implementation (ADR-003)."""

    def __init__(self, *, client: Any, bus_name: str, source: str = EVENT_SOURCE) -> None:
        if not bus_name.strip():
            raise ValueError("EventBridge bus name is required.")
        self._client = client
        self._bus_name = bus_name.strip()
        self._source = source.strip() or EVENT_SOURCE

    def publish(self, event: DomainEvent) -> None:
        response = self._client.put_events(
            Entries=[
                {
                    "Source": self._source,
                    "DetailType": event.event_type,
                    "EventBusName": self._bus_name,
                    "Detail": json.dumps(event.as_detail(), separators=(",", ":")),
                }
            ]
        )
        failed = int(response.get("FailedEntryCount") or 0)
        if failed:
            entries = response.get("Entries") or []
            raise ConnectionError(f"EventBridge PutEvents failed ({failed}): {entries[:3]!r}")


def build_event_publisher(settings: Settings) -> EventBridgePublisher | None:
    """None when AEGIS_AWS_ENDPOINT is unset (messaging disabled)."""
    if not settings.aws_endpoint.strip():
        return None
    bus = settings.event_bus_name.strip() or EVENT_BUS_NAME
    return EventBridgePublisher(client=boto3_client("events", settings), bus_name=bus)
