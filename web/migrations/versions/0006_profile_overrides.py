"""A profile's own DNS and MTU, and the digest of the config last issued to it.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the overrides, empty, and the digest, filled in when the panel starts."""
    with op.batch_alter_table("profile") as batch:
        batch.add_column(sa.Column("dns", sa.String(), nullable=True))
        batch.add_column(sa.Column("mtu", sa.Integer(), nullable=True))
    with op.batch_alter_table("awg_peer") as batch:
        batch.add_column(sa.Column("issued_digest", sa.String(), nullable=True))


def downgrade() -> None:
    """Drop the overrides and the digest."""
    with op.batch_alter_table("awg_peer") as batch:
        batch.drop_column("issued_digest")
    with op.batch_alter_table("profile") as batch:
        batch.drop_column("mtu")
        batch.drop_column("dns")
