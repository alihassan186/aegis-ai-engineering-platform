"""Incident domain public API."""

from aegis.domain.incidents.entity import Incident, StateTransition
from aegis.domain.incidents.enums import IncidentState, Severity
from aegis.domain.incidents.exceptions import InvalidTransitionError
from aegis.domain.incidents.fingerprint import compute_fingerprint
from aegis.domain.incidents.transitions import ALLOWED_TRANSITIONS, can_transition

__all__ = [
    "ALLOWED_TRANSITIONS",
    "Incident",
    "IncidentState",
    "InvalidTransitionError",
    "Severity",
    "StateTransition",
    "can_transition",
    "compute_fingerprint",
]
