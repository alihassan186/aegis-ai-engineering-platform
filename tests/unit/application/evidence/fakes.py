"""In-memory EvidenceRepository for application unit tests."""

from __future__ import annotations

from uuid import UUID

from aegis.domain.evidence import Evidence


class FakeEvidenceRepository:
    def __init__(self) -> None:
        self.items: list[Evidence] = []

    async def add(self, evidence: Evidence) -> Evidence:
        self.items.append(evidence)
        return evidence

    async def list_by_incident(self, incident_id: UUID) -> list[Evidence]:
        return [item for item in self.items if item.incident_id == incident_id]
