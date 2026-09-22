"""Persist an RCA version. Does not transition the incident to identified."""

from __future__ import annotations

from uuid import UUID

from aegis.core.protocols import RcaRepository
from aegis.domain.rca.entity import RcaReport


class RecordRca:
    def __init__(self, repository: RcaRepository) -> None:
        self._repository = repository

    async def persist(self, report: RcaReport) -> RcaReport:
        return await self._repository.add(report)

    async def list_for_incident(self, incident_id: UUID) -> list[RcaReport]:
        return await self._repository.list_by_incident(incident_id)
