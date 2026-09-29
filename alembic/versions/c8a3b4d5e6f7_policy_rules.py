"""Policy rules and admin change history (FR-066).

Revision ID: c8a3b4d5e6f7
Revises: b7f2a3c4d5e6
Create Date: 2026-09-28 21:45:00.000000

"""

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c8a3b4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "b7f2a3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SEED_AT = datetime(2026, 9, 28, tzinfo=timezone.utc)
_SEED_ACTOR = "system:seed"


def upgrade() -> None:
    op.create_table(
        "policy_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("action_class", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=255), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("updated_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tool_name",
            "action_class",
            "scope",
            name="ux_policy_rules_tool_class_scope",
        ),
    )
    op.create_index("ix_policy_rules_tool_name", "policy_rules", ["tool_name"])
    op.create_table(
        "policy_rule_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=True),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_rule_changes_rule_id", "policy_rule_changes", ["rule_id"])
    op.bulk_insert(
        sa.table(
            "policy_rules",
            sa.column("id", sa.Uuid()),
            sa.column("tool_name", sa.String()),
            sa.column("action_class", sa.String()),
            sa.column("scope", sa.String()),
            sa.column("allowed", sa.Boolean()),
            sa.column("reason", sa.String()),
            sa.column("created_by", sa.String()),
            sa.column("updated_by", sa.String()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            _seed_row(
                "a1111111-0000-4000-8000-000000000001",
                "retrieve_knowledge",
                "seed: knowledge retrieve",
            ),
            _seed_row(
                "a1111111-0000-4000-8000-000000000002",
                "fetch_signals",
                "seed: observability signals",
            ),
            _seed_row(
                "a1111111-0000-4000-8000-000000000003",
                "search_code",
                "seed: code search",
            ),
            _seed_row(
                "a1111111-0000-4000-8000-000000000004",
                "list_deploys",
                "seed: code deploys",
            ),
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_policy_rule_changes_rule_id", table_name="policy_rule_changes")
    op.drop_table("policy_rule_changes")
    op.drop_index("ix_policy_rules_tool_name", table_name="policy_rules")
    op.drop_table("policy_rules")


def _seed_row(rule_id: str, tool_name: str, reason: str) -> dict[str, object]:
    return {
        "id": UUID(rule_id),
        "tool_name": tool_name,
        "action_class": "read",
        "scope": "*",
        "allowed": True,
        "reason": reason,
        "created_by": _SEED_ACTOR,
        "updated_by": _SEED_ACTOR,
        "created_at": _SEED_AT,
        "updated_at": _SEED_AT,
    }
