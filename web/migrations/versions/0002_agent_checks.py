"""Healthchecks, and interfaces discovered from the agent rather than typed in.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the check log, the enabled flag, and let operator fields start empty."""
    op.create_table(
        "agent_check",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("awg", sa.String(), nullable=True),
        sa.Column("xray", sa.String(), nullable=True),
        sa.Column("interfaces", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["node_id"], ["node.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_check_node_id", "agent_check", ["node_id"])
    op.create_index("ix_agent_check_checked_at", "agent_check", ["checked_at"])

    # An interface typed in by hand before this revision was already in use.
    with op.batch_alter_table("interface") as batch:
        batch.add_column(
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch.alter_column("address", existing_type=sa.String(), nullable=True)
        batch.alter_column("pool", existing_type=sa.String(), nullable=True)
        batch.alter_column("endpoint_host", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    """Drop the check log and the flag. Interfaces never configured must go first."""
    op.execute(
        "DELETE FROM interface WHERE address IS NULL OR pool IS NULL "
        "OR endpoint_host IS NULL"
    )
    with op.batch_alter_table("interface") as batch:
        batch.alter_column("endpoint_host", existing_type=sa.String(), nullable=False)
        batch.alter_column("pool", existing_type=sa.String(), nullable=False)
        batch.alter_column("address", existing_type=sa.String(), nullable=False)
        batch.drop_column("enabled")
    op.drop_table("agent_check")
