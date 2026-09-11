"""Versioned domain-event envelope (ADR-003). No boto3.

Publish happens in Step 4.2. Step 4.1 defines the shape and the EventPublisher port.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

# These are not arbitrary/hard-coded values, but stable event "type" and "source" identifiers
# aligning with ADR-003 and the event versioning strategy.
# - INCIDENT_OPENED_V1: Explicit event type, scoped and versioned ("incident.opened.v1").
# - EVENT_SOURCE: Domain scoping, identifies aegis incident publisher.
# - SCHEMA_VERSION_V1: Enables schema evolution.

INCIDENT_OPENED_V1 = "incident.opened.v1"       # Versioned event type for detection by consumers
EVENT_SOURCE = "aegis.incidents"                # Logical publisher/source (domain-oriented identity)
SCHEMA_VERSION_V1 = "1"                         # Wire schema version, not event type version


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Wire envelope shared by EventBridge Detail and SQS consumers."""

    event_id: str
    event_type: str
    schema_version: str
    timestamp: str
    correlation_id: str
    incident_id: str

    def as_detail(self) -> dict[str, str]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "incident_id": self.incident_id,
        }


def incident_opened_v1(
    *,
    incident_id: str,
    correlation_id: str,
    event_id: str | None = None,
    timestamp: datetime | None = None,
) -> DomainEvent:
    """First event type: incident persisted as open (FR-020 transport)."""
    incident = incident_id.strip()
    correlation = correlation_id.strip()
    if not incident:
        raise ValueError("incident_id is required.")
    if not correlation:
        raise ValueError("correlation_id is required.")
    when = timestamp or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return DomainEvent(
        event_id=(event_id or str(uuid4())).strip(),
        event_type=INCIDENT_OPENED_V1,
        schema_version=SCHEMA_VERSION_V1,
        timestamp=when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        correlation_id=correlation,
        incident_id=incident,
    )
