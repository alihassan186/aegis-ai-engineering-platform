"""SQLAlchemy ORM model for incident state transitions (FR-004)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis.infrastructure.database.base import Base

if TYPE_CHECKING:
    from aegis.infrastructure.database.models.incident import IncidentModel


class IncidentStateHistoryModel(Base):
    __tablename__ = "incident_state_history"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_state: Mapped[str] = mapped_column(String(32), nullable=False)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    transitioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    incident: Mapped[IncidentModel] = relationship(
        "IncidentModel",
        back_populates="state_history",
    )
