"""Incident lifecycle states and severity (FR-003, FR-005)."""

from enum import StrEnum


class IncidentState(StrEnum):
    """Lifecycle states from incident-flow.md §1 (FR-003)."""

    OPEN = "open"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    REMEDIATING = "remediating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Severity(StrEnum):
    """Impact classification associated with an incident (FR-005)."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
