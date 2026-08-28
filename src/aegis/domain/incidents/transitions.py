"""Allowed incident state transitions (incident-flow.md §1).

Happy path is linear. Any in-progress state may move to ``closed``
(false positive, cancelled work, or post-incident review). ``closed``
is terminal. Skipping forward along the happy path is not allowed.
"""

from collections.abc import Mapping

from aegis.domain.incidents.enums import IncidentState
from aegis.domain.incidents.exceptions import InvalidTransitionError

ALLOWED_TRANSITIONS: Mapping[IncidentState, frozenset[IncidentState]] = {
    IncidentState.OPEN: frozenset(
        {IncidentState.INVESTIGATING, IncidentState.CLOSED},
    ),
    IncidentState.INVESTIGATING: frozenset(
        {IncidentState.IDENTIFIED, IncidentState.CLOSED},
    ),
    IncidentState.IDENTIFIED: frozenset(
        {IncidentState.REMEDIATING, IncidentState.CLOSED},
    ),
    IncidentState.REMEDIATING: frozenset(
        {IncidentState.RESOLVED, IncidentState.CLOSED},
    ),
    IncidentState.RESOLVED: frozenset({IncidentState.CLOSED}),
    IncidentState.CLOSED: frozenset(),
}


def can_transition(current: IncidentState, target: IncidentState) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def require_allowed_transition(current: IncidentState, target: IncidentState) -> None:
    if not can_transition(current, target):
        raise InvalidTransitionError(current, target)
