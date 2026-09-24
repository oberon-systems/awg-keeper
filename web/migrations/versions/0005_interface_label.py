"""The server name an interface gives the Amnezia keys issued on it.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the label, empty for every interface there is."""
    with op.batch_alter_table("interface") as batch:
        batch.add_column(sa.Column("label", sa.String(), nullable=True))


def downgrade() -> None:
    """Drop the label."""
    with op.batch_alter_table("interface") as batch:
        batch.drop_column("label")
