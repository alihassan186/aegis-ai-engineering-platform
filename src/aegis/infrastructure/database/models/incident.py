"""SQLAlchemy ORM model for incidents."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis.infrastructure.database.base import Base

if TYPE_CHECKING:
    from aegis.infrastructure.database.models.state_history import IncidentStateHistoryModel


class IncidentModel(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index(
            "ux_incidents_open_fingerprint",
            "fingerprint",
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL AND state = 'open' AND fingerprint IS NOT NULL"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    affected_service: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    owner_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(512), nullable=True)

    state_history: Mapped[list[IncidentStateHistoryModel]] = relationship(
        "IncidentStateHistoryModel",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentStateHistoryModel.transitioned_at",
    )
