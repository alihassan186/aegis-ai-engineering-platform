"""SQLAlchemy inbox for ``incident_id`` + ``event_type`` + ``schema_version``."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.infrastructure.database.models.processed_event import ProcessedEventModel


class SqlAlchemyProcessedEventStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_once(
        self,
        *,
        incident_id: UUID,
        event_type: str,
        schema_version: str,
        event_id: str,
        correlation_id: str,
    ) -> bool:
        stmt = (
            insert(ProcessedEventModel)
            .values(
                incident_id=incident_id,
                event_type=event_type,
                schema_version=schema_version,
                event_id=event_id,
                correlation_id=correlation_id,
                processed_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(constraint="pk_processed_events")
            .returning(ProcessedEventModel.incident_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
