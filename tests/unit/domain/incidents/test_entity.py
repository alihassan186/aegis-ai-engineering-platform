"""Incident entity construction and FR-005 associations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from aegis.domain.incidents import Incident, IncidentState, Severity
from aegis.shared.exceptions import ValidationError


def test_create_opens_incident_with_identity_and_associations() -> None:
    owner_id = uuid4()
    created_at = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)

    incident = Incident.create(
        title="  API errors  ",
        description="  5xx spike  ",
        affected_service=" checkout-api ",
        severity=Severity.CRITICAL,
        owner_id=owner_id,
        created_at=created_at,
    )

    assert isinstance(incident.id, UUID)
    assert incident.title == "API errors"
    assert incident.description == "5xx spike"
    assert incident.affected_service == "checkout-api"
    assert incident.severity is Severity.CRITICAL
    assert incident.owner_id == owner_id
    assert incident.state is IncidentState.OPEN
    assert incident.created_at == created_at
    assert incident.updated_at == created_at
    assert incident.state_history == ()


def test_create_assigns_unique_ids() -> None:
    first = Incident.create(
        title="Latency",
        affected_service="search",
        severity=Severity.MEDIUM,
    )
    second = Incident.create(
        title="Latency",
        affected_service="search",
        severity=Severity.MEDIUM,
    )

    assert first.id != second.id


def test_owner_and_description_are_optional() -> None:
    incident = Incident.create(
        title="Disk full",
        affected_service="worker",
        severity=Severity.LOW,
    )

    assert incident.owner_id is None
    assert incident.description is None


def test_blank_title_is_rejected() -> None:
    with pytest.raises(ValidationError, match="title"):
        Incident.create(
            title="   ",
            affected_service="api",
            severity=Severity.LOW,
        )


def test_blank_affected_service_is_rejected() -> None:
    with pytest.raises(ValidationError, match="affected_service"):
        Incident.create(
            title="Outage",
            affected_service="",
            severity=Severity.HIGH,
        )


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        Incident.create(
            title="Outage",
            affected_service="api",
            severity=Severity.HIGH,
            created_at=datetime(2026, 8, 28, 12, 0),
        )
