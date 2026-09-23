"""Xray clients of profiles, and the traffic and sessions sampled for them.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the client table and the three stats tables."""
    op.create_table(
        "xray_client",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("inbound_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("flow", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profile.id"]),
        sa.ForeignKeyConstraint(["inbound_id"], ["inbound.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_xray_client_profile_id", "xray_client", ["profile_id"], unique=True
    )
    op.create_index("ix_xray_client_inbound_id", "xray_client", ["inbound_id"])
    op.create_index("ix_xray_client_email", "xray_client", ["email"], unique=True)

    op.create_table(
        "peer_counter",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(), nullable=False),
        sa.Column("rx", sa.Integer(), nullable=False),
        sa.Column("tx", sa.Integer(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("sampled_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_peer_counter_profile_id", "peer_counter", ["profile_id"])

    op.create_table(
        "traffic_hour",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(), nullable=False),
        sa.Column("hour", sa.DateTime(), nullable=False),
        sa.Column("rx", sa.Integer(), nullable=False),
        sa.Column("tx", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_traffic_hour_profile_id", "traffic_hour", ["profile_id"])
    op.create_index("ix_traffic_hour_hour", "traffic_hour", ["hour"])

    op.create_table(
        "profile_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("rx", sa.Integer(), nullable=False),
        sa.Column("tx", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_profile_session_profile_id", "profile_session", ["profile_id"])
    op.create_index("ix_profile_session_started_at", "profile_session", ["started_at"])


def downgrade() -> None:
    """Drop the four tables."""
    op.drop_table("profile_session")
    op.drop_table("traffic_hour")
    op.drop_table("peer_counter")
    op.drop_table("xray_client")
