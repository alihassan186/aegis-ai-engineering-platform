"""Notification rows for RCA ready and escalation (FR-027, FR-028).

Revision ID: b7f2a3c4d5e6
Revises: a6e1f2b3c4d5
Create Date: 2026-09-22 23:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7f2a3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "a6e1f2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("service", sa.String(length=255), nullable=False),
        sa.Column("link", sa.String(length=512), nullable=False),
        sa.Column("dedupe_key", sa.String(length=80), nullable=False),
        sa.Column("rca_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id", "dedupe_key", name="ux_notifications_incident_dedupe"),
    )
    op.create_index("ix_notifications_incident_id", "notifications", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_incident_id", table_name="notifications")
    op.drop_table("notifications")
