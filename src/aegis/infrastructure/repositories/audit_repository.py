"""SQLAlchemy ``AuditRepository`` — INSERT + SELECT only (THR-004)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.domain.audit.entity import GENESIS_HASH, AuditEntry
from aegis.domain.gateway.enums import ActionClass, GatewayVerdict
from aegis.infrastructure.database.models.audit import AuditLogModel


class SqlAlchemyAuditRepository:
    """No ``update`` / ``delete`` methods. Postgres also forbids mutation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, entry: AuditEntry) -> AuditEntry:
        self._session.add(_to_orm(entry))
        await self._session.flush()
        return entry

    async def get(self, audit_id: UUID) -> AuditEntry | None:
        row = await self._session.get(AuditLogModel, audit_id)
        return None if row is None else _to_domain(row)

    async def list_by_incident(self, incident_id: str) -> list[AuditEntry]:
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.incident_id == incident_id)
            .order_by(AuditLogModel.created_at.asc(), AuditLogModel.id.asc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars().all()]

    async def latest_hash(self) -> str:
        stmt = select(AuditLogModel.row_hash).order_by(AuditLogModel.created_at.desc()).limit(1)
        result = await self._session.execute(stmt)
        digest = result.scalar_one_or_none()
        return digest or GENESIS_HASH


def _to_orm(entry: AuditEntry) -> AuditLogModel:
    return AuditLogModel(
        id=entry.id,
        actor=entry.actor,
        action=entry.action,
        input=entry.input,
        output=entry.output,
        decision=entry.decision.value,
        reason=entry.reason,
        incident_id=entry.incident_id,
        action_class=None if entry.action_class is None else entry.action_class.value,
        created_at=entry.created_at,
        prev_hash=entry.prev_hash,
        row_hash=entry.row_hash,
    )


def _to_domain(row: AuditLogModel) -> AuditEntry:
    return AuditEntry(
        id=row.id,
        actor=row.actor,
        action=row.action,
        input=dict(row.input or {}),
        output=None if row.output is None else dict(row.output),
        decision=GatewayVerdict(row.decision),
        reason=row.reason,
        incident_id=row.incident_id,
        action_class=None if row.action_class is None else ActionClass(row.action_class),
        created_at=row.created_at,
        prev_hash=row.prev_hash,
        row_hash=row.row_hash,
    )
