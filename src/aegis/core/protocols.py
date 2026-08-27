"""Repository and service ports.

Concrete implementations belong in ``aegis.infrastructure`` (Step 1.6).
"""

from typing import Protocol


class IncidentRepository(Protocol):
    """Persistence port for incident aggregates."""
