"""Empty baseline — no tables yet (incident schema is Step 1.6).

Revision ID: b07e289b8091
Revises:
Create Date: 2026-08-27 23:58:31.428089

"""

from typing import Sequence, Union

revision: str = "b07e289b8091"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
