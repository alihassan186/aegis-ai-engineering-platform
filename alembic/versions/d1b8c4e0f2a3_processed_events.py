"""Inbox table for investigation worker idempotency (ADR-003).

Revision ID: d1b8c4e0f2a3
Revises: a3f91c2d4e80
Create Date: 2026-09-13 21:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1b8c4e0f2a3"
down_revision: Union[str, Sequence[str], None] = "a3f91c2d4e80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "incident_id",
            "event_type",
            "schema_version",
            name="pk_processed_events",
        ),
    )


def downgrade() -> None:
    op.drop_table("processed_events")
