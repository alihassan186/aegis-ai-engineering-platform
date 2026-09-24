"""SQLAlchemy ``NotificationRepository`` with dedupe on (incident, key)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.domain.notifications.entity import Notification
from aegis.domain.notifications.enums import NotificationKind
from aegis.infrastructure.database.models.notification import NotificationModel


class SqlAlchemyNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_once(self, notification: Notification) -> bool:
        """Insert or no-op. Uses a savepoint so a duplicate does not undo RCA."""
        nested = await self._session.begin_nested()
        try:
            self._session.add(_to_orm(notification))
            await self._session.flush()
        except IntegrityError:
            await nested.rollback()
            return False
        await nested.commit()
        return True

    async def list_by_incident(self, incident_id: UUID) -> list[Notification]:
        stmt = (
            select(NotificationModel)
            .where(NotificationModel.incident_id == incident_id)
            .order_by(NotificationModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [_to_domain(row) for row in result.scalars().all()]


def _to_orm(item: Notification) -> NotificationModel:
    return NotificationModel(
        id=item.id,
        incident_id=item.incident_id,
        kind=item.kind.value,
        event_type=item.event_type,
        reason=item.reason,
        severity=item.severity,
        service=item.service,
        link=item.link,
        dedupe_key=item.dedupe_key,
        rca_version=item.rca_version,
        created_at=item.created_at,
    )


def _to_domain(row: NotificationModel) -> Notification:
    return Notification(
        id=row.id,
        incident_id=row.incident_id,
        kind=NotificationKind(row.kind),
        event_type=row.event_type,
        reason=row.reason,
        severity=row.severity,
        service=row.service,
        link=row.link,
        dedupe_key=row.dedupe_key,
        rca_version=row.rca_version,
        created_at=row.created_at,
    )
