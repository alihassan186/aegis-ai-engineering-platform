"""Policy rule version + audit policy_version / deny_all (Step 5.11).

Adding columns is DDL, so the 5.6 UPDATE/DELETE triggers do not fire and the
audit log stays append-only. Existing audit rows get ``policy_version=''`` and
``deny_all=false`` (and still hash identically; see ``AuditEntry.create``).

Revision ID: e7a1b2c3d4f5
Revises: d9e4f5a6b7c8
Create Date: 2026-10-07 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7a1b2c3d4f5"
down_revision: Union[str, Sequence[str], None] = "d9e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "policy_rules",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "audit_log",
        sa.Column("policy_version", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "audit_log",
        sa.Column("deny_all", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("audit_log", "deny_all")
    op.drop_column("audit_log", "policy_version")
    op.drop_column("policy_rules", "version")
