"""RCA reports linked to incidents (FR-030, FR-035).

Revision ID: f5d0b3c4e1a2
Revises: e4c9a1b2d3f0
Create Date: 2026-09-22 22:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f5d0b3c4e1a2"
down_revision: Union[str, Sequence[str], None] = "e4c9a1b2d3f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rca_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("version_kind", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("contributing_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("finding_status", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("evidence_citations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommended_actions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id", "version", name="ux_rca_reports_incident_version"),
    )
    op.create_index("ix_rca_reports_incident_id", "rca_reports", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_rca_reports_incident_id", table_name="rca_reports")
    op.drop_table("rca_reports")
