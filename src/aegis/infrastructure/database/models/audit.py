"""SQLAlchemy model for AUDIT_LOG (FR-100). Append-only at the table."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aegis.infrastructure.database.base import Base


class AuditLogModel(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_incident_id", "incident_id"),
        Index("ix_audit_log_created_at", "created_at"),
        Index("ix_audit_log_actor", "actor"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    incident_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    policy_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default=""
    )
    deny_all: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
