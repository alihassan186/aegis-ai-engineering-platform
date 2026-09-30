"""SQLAlchemy model for POLICY_RULE (FR-066)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from aegis.infrastructure.database.base import Base


class PolicyRuleModel(Base):
    __tablename__ = "policy_rules"
    __table_args__ = (
        UniqueConstraint(
            "tool_name",
            "action_class",
            "scope",
            name="ux_policy_rules_tool_class_scope",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    action_class: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[str] = mapped_column(String(255), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
