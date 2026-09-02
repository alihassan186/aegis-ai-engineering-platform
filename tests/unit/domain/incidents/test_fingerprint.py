"""Fingerprint is a stable key from service + scenario + UTC hour (FR-007)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from aegis.domain.incidents.fingerprint import UNSPECIFIED_SCENARIO, compute_fingerprint
from aegis.shared.exceptions import ValidationError

_HOUR = datetime(2026, 9, 2, 14, 30, tzinfo=UTC)


def test_same_service_scenario_and_hour_match() -> None:
    first = compute_fingerprint(
        affected_service="payment",
        scenario="latency_spike",
        occurred_at=_HOUR,
    )
    second = compute_fingerprint(
        affected_service="  Payment ",
        scenario="Latency_Spike",
        occurred_at=datetime(2026, 9, 2, 14, 59, tzinfo=UTC),
    )

    assert first == second
    assert first == "v1|payment|latency_spike|2026-09-02T14"


def test_blank_scenario_uses_unspecified() -> None:
    key = compute_fingerprint(
        affected_service="payment",
        scenario=None,
        occurred_at=_HOUR,
    )

    assert f"|{UNSPECIFIED_SCENARIO}|" in key
    assert key == compute_fingerprint(
        affected_service="payment",
        scenario="  ",
        occurred_at=_HOUR,
    )


def test_different_service_or_scenario_differs() -> None:
    base = compute_fingerprint(
        affected_service="payment",
        scenario="latency_spike",
        occurred_at=_HOUR,
    )
    other_service = compute_fingerprint(
        affected_service="order",
        scenario="latency_spike",
        occurred_at=_HOUR,
    )
    other_scenario = compute_fingerprint(
        affected_service="payment",
        scenario="db_exhaustion",
        occurred_at=_HOUR,
    )

    assert base != other_service
    assert base != other_scenario


def test_next_utc_hour_is_a_new_key() -> None:
    current = compute_fingerprint(
        affected_service="payment",
        scenario="latency_spike",
        occurred_at=_HOUR,
    )
    next_hour = compute_fingerprint(
        affected_service="payment",
        scenario="latency_spike",
        occurred_at=datetime(2026, 9, 2, 15, 0, tzinfo=UTC),
    )

    assert current != next_hour


def test_offset_timezone_is_bucketed_in_utc() -> None:
    plus_one = timezone(timedelta(hours=1))
    local = compute_fingerprint(
        affected_service="payment",
        scenario="latency_spike",
        occurred_at=datetime(2026, 9, 2, 15, 30, tzinfo=plus_one),
    )
    utc = compute_fingerprint(
        affected_service="payment",
        scenario="latency_spike",
        occurred_at=datetime(2026, 9, 2, 14, 30, tzinfo=UTC),
    )

    assert local == utc


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        compute_fingerprint(
            affected_service="payment",
            scenario="latency_spike",
            occurred_at=datetime(2026, 9, 2, 14, 30),
        )


def test_blank_service_is_rejected() -> None:
    with pytest.raises(ValidationError, match="affected_service"):
        compute_fingerprint(
            affected_service="  ",
            scenario="latency_spike",
            occurred_at=_HOUR,
        )
