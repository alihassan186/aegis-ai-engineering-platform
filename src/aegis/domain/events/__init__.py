"""Domain event contracts. No boto3 (ADR-001)."""

from aegis.domain.events.envelope import (
    EVENT_SOURCE,
    INCIDENT_OPENED_V1,
    SCHEMA_VERSION_V1,
    DomainEvent,
    incident_opened_v1,
)

__all__ = [
    "EVENT_SOURCE",
    "INCIDENT_OPENED_V1",
    "SCHEMA_VERSION_V1",
    "DomainEvent",
    "incident_opened_v1",
]
