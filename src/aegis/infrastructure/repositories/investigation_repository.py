"""SQLAlchemy implementation of ``InvestigationProgressRepository``."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.domain.investigation.enums import InvestigationRunStatus, InvestigationStepStatus
from aegis.domain.investigation.progress import InvestigationProgress, InvestigationStep
from aegis.infrastructure.database.models.investigation import (
    InvestigationProgressModel,
    InvestigationStepModel,
)


class SqlAlchemyInvestigationProgressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_incident(self, incident_id: UUID) -> InvestigationProgress | None:
        row = await self._session.get(InvestigationProgressModel, incident_id)
        if row is None:
            return None
        stmt = (
            select(InvestigationStepModel)
            .where(InvestigationStepModel.incident_id == incident_id)
            .order_by(InvestigationStepModel.occurred_at.asc())
        )
        result = await self._session.execute(stmt)
        steps = [_step_to_domain(item) for item in result.scalars().all()]
        return InvestigationProgress(
            incident_id=row.incident_id,
            hops=row.hops,
            status=InvestigationRunStatus(row.status),
            escalate_reason=row.escalate_reason,
            paused=row.paused,
            steps=steps,
            updated_at=row.updated_at,
        )

    async def save(self, progress: InvestigationProgress) -> InvestigationProgress:
        existing = await self._session.get(InvestigationProgressModel, progress.incident_id)
        if existing is None:
            self._session.add(_progress_to_orm(progress))
        else:
            existing.hops = progress.hops
            existing.status = progress.status.value
            existing.escalate_reason = progress.escalate_reason
            existing.paused = progress.paused
            existing.updated_at = progress.updated_at
        await self._session.execute(
            delete(InvestigationStepModel).where(
                InvestigationStepModel.incident_id == progress.incident_id
            )
        )
        for step in progress.steps:
            self._session.add(_step_to_orm(step))
        await self._session.flush()
        return progress


def _progress_to_orm(progress: InvestigationProgress) -> InvestigationProgressModel:
    return InvestigationProgressModel(
        incident_id=progress.incident_id,
        hops=progress.hops,
        status=progress.status.value,
        escalate_reason=progress.escalate_reason,
        paused=progress.paused,
        updated_at=progress.updated_at,
    )


def _step_to_orm(step: InvestigationStep) -> InvestigationStepModel:
    return InvestigationStepModel(
        id=step.id,
        incident_id=step.incident_id,
        name=step.name,
        status=step.status.value,
        detail=step.detail,
        occurred_at=step.occurred_at,
    )


def _step_to_domain(row: InvestigationStepModel) -> InvestigationStep:
    return InvestigationStep(
        id=row.id,
        incident_id=row.incident_id,
        name=row.name,
        status=InvestigationStepStatus(row.status),
        detail=row.detail,
        occurred_at=row.occurred_at,
    )
