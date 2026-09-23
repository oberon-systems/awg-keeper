"""Xray inbounds discovered from the agent, and the inbounds each check saw.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the inbound table and the inbounds column of the check log."""
    op.create_table(
        "inbound",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("protocol", sa.String(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("network", sa.String(), nullable=False),
        sa.Column("security", sa.String(), nullable=False),
        sa.Column("server_names", sa.JSON(), nullable=True),
        sa.Column("short_ids", sa.JSON(), nullable=True),
        sa.Column("public_key", sa.String(), nullable=True),
        sa.Column("endpoint_host", sa.String(), nullable=True),
        sa.Column("flow", sa.String(), nullable=True),
        sa.Column("fingerprint", sa.String(), nullable=True),
        sa.Column("short_id", sa.String(), nullable=True),
        sa.Column("label", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["node_id"], ["node.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inbound_node_id", "inbound", ["node_id"])

    with op.batch_alter_table("agent_check") as batch:
        batch.add_column(sa.Column("inbounds", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Drop the column and the table."""
    with op.batch_alter_table("agent_check") as batch:
        batch.drop_column("inbounds")
    op.drop_table("inbound")
