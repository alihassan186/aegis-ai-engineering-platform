"""SQLAlchemy implementation of ``IncidentRepository`` (ADR-001, ADR-002)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aegis.core.protocols import IncidentFilters
from aegis.domain.incidents.entity import Incident
from aegis.infrastructure.database.models.incident import IncidentModel
from aegis.infrastructure.repositories.mappers import apply_to_orm, to_domain, to_orm
from aegis.shared.exceptions import NotFoundError


class SqlAlchemyIncidentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, incident: Incident) -> Incident:
        row = to_orm(incident)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row, attribute_names=["state_history"])
        return to_domain(row)

    async def get_by_id(self, id: UUID) -> Incident | None:
        row = await self._load(id)
        if row is None:
            return None
        return to_domain(row)

    async def list(self, filters: IncidentFilters) -> list[Incident]:
        stmt = (
            select(IncidentModel)
            .options(selectinload(IncidentModel.state_history))
            .where(IncidentModel.deleted_at.is_(None))
            .order_by(IncidentModel.created_at.desc())
        )
        if filters.state is not None:
            stmt = stmt.where(IncidentModel.state == filters.state.value)
        if filters.severity is not None:
            stmt = stmt.where(IncidentModel.severity == filters.severity.value)
        if filters.affected_service is not None:
            stmt = stmt.where(IncidentModel.affected_service == filters.affected_service)
        if filters.owner_id is not None:
            stmt = stmt.where(IncidentModel.owner_id == filters.owner_id)
        if filters.created_after is not None:
            stmt = stmt.where(IncidentModel.created_at >= filters.created_after)
        if filters.created_before is not None:
            stmt = stmt.where(IncidentModel.created_at <= filters.created_before)

        result = await self._session.execute(stmt)
        return [to_domain(row) for row in result.scalars().unique().all()]

    async def save(self, incident: Incident) -> Incident:
        row = await self._load(incident.id)
        if row is None:
            raise NotFoundError(f"Incident '{incident.id}' was not found.")
        apply_to_orm(incident, row)
        await self._session.flush()
        await self._session.refresh(row, attribute_names=["state_history"])
        return to_domain(row)

    async def _load(self, incident_id: UUID) -> IncidentModel | None:
        stmt = (
            select(IncidentModel)
            .options(selectinload(IncidentModel.state_history))
            .where(
                IncidentModel.id == incident_id,
                IncidentModel.deleted_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
