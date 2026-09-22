"""Inbox row for worker idempotency (ADR-003)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, PrimaryKeyConstraint, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from aegis.infrastructure.database.base import Base


class ProcessedEventModel(Base):
    __tablename__ = "processed_events"
    __table_args__ = (
        PrimaryKeyConstraint(
            "incident_id",
            "event_type",
            "schema_version",
            name="pk_processed_events",
        ),
    )

    incident_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str] = mapped_column(Text, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
