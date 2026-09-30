"""SQLAlchemy model for policy rule change history (before 5.6 AUDIT_LOG)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aegis.infrastructure.database.base import Base


class PolicyRuleChangeModel(Base):
    __tablename__ = "policy_rule_changes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    rule_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
