"""Add incident fingerprint for open-incident dedup (FR-007).

Revision ID: a3f91c2d4e80
Revises: c4e81f2a9b70
Create Date: 2026-09-02 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f91c2d4e80"
down_revision: Union[str, Sequence[str], None] = "c4e81f2a9b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("incidents", sa.Column("fingerprint", sa.String(length=512), nullable=True))
    op.create_index(
        "ux_incidents_open_fingerprint",
        "incidents",
        ["fingerprint"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND state = 'open' AND fingerprint IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("ux_incidents_open_fingerprint", table_name="incidents")
    op.drop_column("incidents", "fingerprint")
