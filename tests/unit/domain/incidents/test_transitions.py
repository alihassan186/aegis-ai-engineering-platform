"""Incident state machine rules from incident-flow.md §1."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aegis.domain.incidents import (
    Incident,
    IncidentState,
    InvalidTransitionError,
    Severity,
    can_transition,
)

_HAPPY_PATH: tuple[tuple[IncidentState, IncidentState], ...] = (
    (IncidentState.OPEN, IncidentState.INVESTIGATING),
    (IncidentState.INVESTIGATING, IncidentState.IDENTIFIED),
    (IncidentState.IDENTIFIED, IncidentState.REMEDIATING),
    (IncidentState.REMEDIATING, IncidentState.RESOLVED),
    (IncidentState.RESOLVED, IncidentState.CLOSED),
)

_EARLY_CLOSE: tuple[IncidentState, ...] = (
    IncidentState.OPEN,
    IncidentState.INVESTIGATING,
    IncidentState.IDENTIFIED,
    IncidentState.REMEDIATING,
)


def _open_incident() -> Incident:
    return Incident.create(
        title="Checkout latency",
        affected_service="payments-api",
        severity=Severity.HIGH,
    )


def test_open_to_investigating_is_allowed() -> None:
    incident = _open_incident()

    incident.transition_to(IncidentState.INVESTIGATING)

    assert incident.state is IncidentState.INVESTIGATING


def test_open_to_resolved_is_rejected() -> None:
    incident = _open_incident()

    with pytest.raises(InvalidTransitionError) as caught:
        incident.transition_to(IncidentState.RESOLVED)

    assert caught.value.current is IncidentState.OPEN
    assert caught.value.target is IncidentState.RESOLVED
    assert incident.state is IncidentState.OPEN
    assert incident.state_history == ()


@pytest.mark.parametrize(("current", "target"), _HAPPY_PATH)
def test_happy_path_transition_is_allowed(
    current: IncidentState,
    target: IncidentState,
) -> None:
    assert can_transition(current, target)


@pytest.mark.parametrize("current", _EARLY_CLOSE)
def test_early_close_from_in_progress_state_is_allowed(current: IncidentState) -> None:
    assert can_transition(current, IncidentState.CLOSED)


def test_full_happy_path_reaches_closed() -> None:
    incident = _open_incident()

    for _, target in _HAPPY_PATH:
        incident.transition_to(target)

    assert incident.state is IncidentState.CLOSED
    assert [step.to_state for step in incident.state_history] == [
        target for _, target in _HAPPY_PATH
    ]


def test_closed_is_terminal() -> None:
    incident = _open_incident()
    incident.transition_to(IncidentState.CLOSED)

    for target in IncidentState:
        with pytest.raises(InvalidTransitionError):
            incident.transition_to(target)


def test_cannot_skip_or_reverse_along_happy_path() -> None:
    illegal = (
        (IncidentState.OPEN, IncidentState.IDENTIFIED),
        (IncidentState.OPEN, IncidentState.REMEDIATING),
        (IncidentState.OPEN, IncidentState.RESOLVED),
        (IncidentState.INVESTIGATING, IncidentState.OPEN),
        (IncidentState.INVESTIGATING, IncidentState.REMEDIATING),
        (IncidentState.INVESTIGATING, IncidentState.RESOLVED),
        (IncidentState.IDENTIFIED, IncidentState.OPEN),
        (IncidentState.IDENTIFIED, IncidentState.INVESTIGATING),
        (IncidentState.IDENTIFIED, IncidentState.RESOLVED),
        (IncidentState.REMEDIATING, IncidentState.IDENTIFIED),
        (IncidentState.REMEDIATING, IncidentState.INVESTIGATING),
        (IncidentState.RESOLVED, IncidentState.REMEDIATING),
        (IncidentState.RESOLVED, IncidentState.OPEN),
        (IncidentState.CLOSED, IncidentState.OPEN),
    )

    for current, target in illegal:
        assert can_transition(current, target) is False


def test_every_state_pair_matches_incident_flow_rules() -> None:
    allowed = set(_HAPPY_PATH) | {(state, IncidentState.CLOSED) for state in _EARLY_CLOSE}

    for current in IncidentState:
        for target in IncidentState:
            expected = (current, target) in allowed
            assert can_transition(current, target) is expected


def test_state_history_records_timestamp_on_each_transition() -> None:
    incident = _open_incident()
    before = datetime.now(timezone.utc)

    incident.transition_to(IncidentState.INVESTIGATING)

    after = datetime.now(timezone.utc)
    assert len(incident.state_history) == 1
    record = incident.state_history[0]
    assert record.from_state is IncidentState.OPEN
    assert record.to_state is IncidentState.INVESTIGATING
    assert record.occurred_at.tzinfo is not None
    assert before <= record.occurred_at <= after
    assert incident.updated_at == record.occurred_at


def test_state_history_is_immutable_from_outside() -> None:
    incident = _open_incident()
    incident.transition_to(IncidentState.INVESTIGATING)
    history = incident.state_history

    with pytest.raises(AttributeError):
        history.append(history[0])  # type: ignore[attr-defined]

    assert len(incident.state_history) == 1
