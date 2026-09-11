"""Domain event envelope (Step 4.1). No network."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aegis.core.events import INCIDENT_OPENED_V1, incident_opened_v1


def test_incident_opened_v1_fills_envelope() -> None:
    event = incident_opened_v1(
        incident_id="11111111-1111-1111-1111-111111111111",
        correlation_id="corr-1",
        event_id="evt-1",
        timestamp=datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
    )
    assert event.event_type == INCIDENT_OPENED_V1
    assert event.schema_version == "1"
    assert event.timestamp == "2026-09-11T12:00:00Z"
    assert event.as_detail()["incident_id"] == event.incident_id


def test_incident_opened_v1_rejects_blank_ids() -> None:
    with pytest.raises(ValueError, match="incident_id"):
        incident_opened_v1(incident_id="  ", correlation_id="c")
    with pytest.raises(ValueError, match="correlation_id"):
        incident_opened_v1(incident_id="i", correlation_id="")
