"""Evidence table linked to incidents (FR-017, FR-018).

Revision ID: e4c9a1b2d3f0
Revises: d1b8c4e0f2a3
Create Date: 2026-09-20 20:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4c9a1b2d3f0"
down_revision: Union[str, Sequence[str], None] = "d1b8c4e0f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("content_ref", sa.String(length=1024), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_incident_id", "evidence", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_evidence_incident_id", table_name="evidence")
    op.drop_table("evidence")
