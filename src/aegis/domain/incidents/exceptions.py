"""Incident domain errors."""

from aegis.domain.incidents.enums import IncidentState
from aegis.shared.exceptions import DomainError


class InvalidTransitionError(DomainError):
    """Raised when an incident cannot move to the requested state."""

    def __init__(self, current: IncidentState, target: IncidentState) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition incident from '{current}' to '{target}'.")
