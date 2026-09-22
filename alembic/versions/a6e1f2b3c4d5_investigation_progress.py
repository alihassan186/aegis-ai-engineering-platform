"""Investigation progress and steps (FR-022, FR-023).

Revision ID: a6e1f2b3c4d5
Revises: f5d0b3c4e1a2
Create Date: 2026-09-22 23:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a6e1f2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "f5d0b3c4e1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investigation_progress",
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("hops", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("escalate_reason", sa.String(length=64), nullable=False),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("incident_id"),
    )
    op.create_table(
        "investigation_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investigation_steps_incident_id",
        "investigation_steps",
        ["incident_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_investigation_steps_incident_id", table_name="investigation_steps")
    op.drop_table("investigation_steps")
    op.drop_table("investigation_progress")
