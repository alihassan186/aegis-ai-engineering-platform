"""SQLAlchemy implementation of ``EvidenceRepository`` (ADR-001, ADR-002)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.domain.evidence.entity import Evidence
from aegis.domain.evidence.enums import EvidenceKind, EvidenceSource
from aegis.infrastructure.database.models.evidence import EvidenceModel


class SqlAlchemyEvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, evidence: Evidence) -> Evidence:
        self._session.add(_to_orm(evidence))
        await self._session.flush()
        return evidence

    async def list_by_incident(self, incident_id: UUID) -> list[Evidence]:
        stmt = (
            select(EvidenceModel)
            .where(EvidenceModel.incident_id == incident_id)
            .order_by(EvidenceModel.collected_at.asc(), EvidenceModel.id.asc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars().all()]


def _to_orm(evidence: Evidence) -> EvidenceModel:
    return EvidenceModel(
        id=evidence.id,
        incident_id=evidence.incident_id,
        source=evidence.source.value,
        kind=evidence.kind.value,
        content_ref=evidence.content_ref,
        summary=evidence.summary,
        metadata_=dict(evidence.metadata),
        collected_at=evidence.collected_at,
    )


def _to_domain(row: EvidenceModel) -> Evidence:
    return Evidence(
        id=row.id,
        incident_id=row.incident_id,
        source=EvidenceSource(row.source),
        kind=EvidenceKind(row.kind),
        content_ref=row.content_ref,
        summary=row.summary,
        metadata=dict(row.metadata_ or {}),
        collected_at=row.collected_at,
    )
