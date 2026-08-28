"""Repository and service ports.

Concrete implementations belong in ``aegis.infrastructure`` (Step 1.6).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from aegis.domain.incidents.entity import Incident
from aegis.domain.incidents.enums import IncidentState, Severity


@dataclass(frozen=True, slots=True)
class IncidentFilters:
    """Query options for listing incidents (FR-009)."""

    state: IncidentState | None = None
    severity: Severity | None = None
    affected_service: str | None = None
    owner_id: UUID | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


class IncidentRepository(Protocol):
    """Persistence port for incident aggregates."""

    async def create(self, incident: Incident) -> Incident: ...

    async def get_by_id(self, id: UUID) -> Incident | None: ...

    async def list(self, filters: IncidentFilters) -> list[Incident]: ...

    async def save(self, incident: Incident) -> Incident: ...
