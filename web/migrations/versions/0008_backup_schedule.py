"""When the database is backed up, set from the panel.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the schedule, empty; the panel uses its default until one is saved."""
    op.create_table(
        "backup_schedule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cron", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("keep", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("author", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop the schedule."""
    op.drop_table("backup_schedule")
