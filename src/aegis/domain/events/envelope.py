"""Versioned domain-event envelope (ADR-003). No boto3.

Idempotency key: ``incident_id`` + ``event_type`` + ``schema_version``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

INCIDENT_OPENED_V1 = "incident.opened.v1"
RCA_COMPLETED_V1 = "rca.completed.v1"
RCA_ESCALATED_V1 = "rca.escalated.v1"
EVENT_SOURCE = "aegis.incidents"
SCHEMA_VERSION_V1 = "1"


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

    def idempotency_key(self) -> tuple[str, str, str]:
        return (self.incident_id, self.event_type, self.schema_version)


def incident_opened_v1(
    *,
    incident_id: str,
    correlation_id: str,
    event_id: str | None = None,
    timestamp: datetime | None = None,
) -> DomainEvent:
    """First event type: incident persisted as open (FR-020)."""
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


def _timed_event(
    *,
    event_type: str,
    incident_id: str,
    correlation_id: str,
    event_id: str | None = None,
    timestamp: datetime | None = None,
) -> DomainEvent:
    incident = incident_id.strip()
    correlation = correlation_id.strip() or incident
    if not incident:
        raise ValueError("incident_id is required.")
    when = timestamp or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return DomainEvent(
        event_id=(event_id or str(uuid4())).strip(),
        event_type=event_type,
        schema_version=SCHEMA_VERSION_V1,
        timestamp=when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        correlation_id=correlation,
        incident_id=incident,
    )


def rca_completed_v1(*, incident_id: str, correlation_id: str = "") -> DomainEvent:
    return _timed_event(
        event_type=RCA_COMPLETED_V1,
        incident_id=incident_id,
        correlation_id=correlation_id,
    )


def rca_escalated_v1(*, incident_id: str, correlation_id: str = "") -> DomainEvent:
    return _timed_event(
        event_type=RCA_ESCALATED_V1,
        incident_id=incident_id,
        correlation_id=correlation_id,
    )
