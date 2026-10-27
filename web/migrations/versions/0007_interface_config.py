"""The history of every interface's portable config, newest version current.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the history table, empty; the panel records a baseline when it starts."""
    op.create_table(
        "interface_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interface_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("digest", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("rolled_back_from", sa.Integer(), nullable=True),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("interface_id", "version"),
    )
    op.create_index(
        "ix_interface_config_interface_id", "interface_config", ["interface_id"]
    )
    op.create_index(
        "ix_interface_config_created_at", "interface_config", ["created_at"]
    )


def downgrade() -> None:
    """Drop the history."""
    op.drop_index("ix_interface_config_created_at", "interface_config")
    op.drop_index("ix_interface_config_interface_id", "interface_config")
    op.drop_table("interface_config")
