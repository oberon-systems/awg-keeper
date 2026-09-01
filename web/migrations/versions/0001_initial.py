"""The initial schema: nodes, interfaces, profiles, peers and released addresses.

Revision ID: 0001
Revises:
Create Date: 2026-09-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create every table the panel starts with."""
    op.create_table(
        "node",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_node_name", "node", ["name"], unique=True)

    op.create_table(
        "interface",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("listen_port", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("pool", sa.String(), nullable=False),
        sa.Column("server_public_key", sa.String(), nullable=False),
        sa.Column("endpoint_host", sa.String(), nullable=False),
        sa.Column("dns", sa.String(), nullable=True),
        sa.Column("mtu", sa.Integer(), nullable=True),
        sa.Column("client_allowed_ips", sa.String(), nullable=False),
        sa.Column("keepalive", sa.Integer(), nullable=True),
        sa.Column("obfuscation", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["node_id"], ["node.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interface_node_id", "interface", ["node_id"])

    op.create_table(
        "profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_profile_name", "profile", ["name"], unique=True)

    op.create_table(
        "awg_peer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("interface_id", sa.Integer(), nullable=False),
        sa.Column("public_key", sa.String(), nullable=False),
        sa.Column("assigned_ip", sa.String(), nullable=False),
        sa.Column("allowed_ips", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["interface_id"], ["interface.id"]),
        sa.ForeignKeyConstraint(["profile_id"], ["profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_awg_peer_profile_id", "awg_peer", ["profile_id"], unique=True)
    op.create_index("ix_awg_peer_interface_id", "awg_peer", ["interface_id"])
    op.create_index("ix_awg_peer_public_key", "awg_peer", ["public_key"], unique=True)

    op.create_table(
        "released_ip",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interface_id", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["interface_id"], ["interface.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_released_ip_interface_id", "released_ip", ["interface_id"])
    op.create_index("ix_released_ip_address", "released_ip", ["address"])


def downgrade() -> None:
    """Drop everything, in the order the foreign keys allow."""
    op.drop_table("released_ip")
    op.drop_table("awg_peer")
    op.drop_table("profile")
    op.drop_table("interface")
    op.drop_table("node")
