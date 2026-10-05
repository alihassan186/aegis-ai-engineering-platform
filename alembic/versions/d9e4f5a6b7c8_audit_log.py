"""Append-only AUDIT_LOG (FR-100, FR-062, THR-004, NFR-063).

Revision ID: d9e4f5a6b7c8
Revises: c8a3b4d5e6f7
Create Date: 2026-10-04 21:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d9e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c8a3b4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("action_class", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("row_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("row_hash", name="ux_audit_log_row_hash"),
    )
    op.create_index("ix_audit_log_incident_id", "audit_log", ["incident_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_actor", "audit_log", ["actor"])
    op.execute(
        sa.text(
            "COMMENT ON TABLE audit_log IS "
            "'Compliance audit; retain separately from operational data (NFR-063).'"
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION aegis_audit_log_immutable()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
              RAISE EXCEPTION 'audit_log is append-only (THR-004)';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER audit_log_forbid_update
            BEFORE UPDATE ON audit_log
            FOR EACH ROW
            EXECUTE FUNCTION aegis_audit_log_immutable()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER audit_log_forbid_delete
            BEFORE DELETE ON audit_log
            FOR EACH ROW
            EXECUTE FUNCTION aegis_audit_log_immutable()
            """
        )
    )
    op.execute(sa.text("REVOKE UPDATE, DELETE ON TABLE audit_log FROM PUBLIC"))


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS audit_log_forbid_delete ON audit_log"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS audit_log_forbid_update ON audit_log"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS aegis_audit_log_immutable()"))
    op.drop_index("ix_audit_log_actor", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_incident_id", table_name="audit_log")
    op.drop_table("audit_log")
