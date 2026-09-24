"""The database.

node_id is a foreign key from day one, so the multi-node case needs no
migration even though v1 accepts a single agent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class Node(SQLModel, table=True):
    """One host running an agent. v1 has exactly one row."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    endpoint: str
    status: str = "unknown"
    last_seen: datetime | None = None
    created_at: datetime = Field(default_factory=_now)


class Interface(SQLModel, table=True):
    """An AmneziaWG interface, and everything a client config needs from it."""

    id: int | None = Field(default=None, primary_key=True)
    node_id: int = Field(foreign_key="node.id", index=True)
    name: str
    # Discovered from the agent disabled; profiles are issued only once enabled.
    enabled: bool = False
    listen_port: int
    # The server side of the tunnel, and the pool peers are allocated from.
    address: str | None = None
    pool: str | None = None
    server_public_key: str
    endpoint_host: str | None = None
    # The server name the Amnezia key carries; the profile name when unset.
    label: str | None = None
    dns: str | None = None
    mtu: int | None = None
    # What the client puts in AllowedIPs: full or split tunnel, per interface.
    client_allowed_ips: str = "0.0.0.0/0"
    keepalive: int | None = 25
    # Jc, Jmin, Jmax, S1, S2, H1-H4. Identical on both ends or the handshake
    # never completes, which is the single most common failure.
    obfuscation: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Inbound(SQLModel, table=True):
    """An Xray inbound, and everything a vless:// link needs from it."""

    id: int | None = Field(default=None, primary_key=True)
    node_id: int = Field(foreign_key="node.id", index=True)
    tag: str
    # Discovered from the agent disabled, like an interface.
    enabled: bool = False
    protocol: str = ""
    port: int = 0
    network: str = "tcp"
    security: str = "none"
    server_names: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    short_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    # Derived on the host; the private half never leaves it.
    public_key: str | None = None
    endpoint_host: str | None = None
    flow: str | None = None
    fingerprint: str | None = None
    short_id: str | None = None
    label: str | None = None


class AgentCheck(SQLModel, table=True):
    """One healthcheck of one agent, kept for check_retention days."""

    __tablename__ = "agent_check"

    id: int | None = Field(default=None, primary_key=True)
    node_id: int = Field(foreign_key="node.id", index=True)
    checked_at: datetime = Field(default_factory=_now, index=True)
    status: str
    latency_ms: float | None = None
    error: str | None = None
    version: str | None = None
    awg: str | None = None
    xray: str | None = None
    interfaces: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    inbounds: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))


class Profile(SQLModel, table=True):
    """A person or a device. Owns zero or one AWG peer and zero or one Xray client."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    note: str | None = None
    enabled: bool = True
    created_at: datetime = Field(default_factory=_now)


class AwgPeer(SQLModel, table=True):
    """A peer. The panel holds the public key and never the private one."""

    __tablename__ = "awg_peer"

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True, unique=True)
    interface_id: int = Field(foreign_key="interface.id", index=True)
    public_key: str = Field(index=True, unique=True)
    assigned_ip: str
    allowed_ips: str = "0.0.0.0/0"
    enabled: bool = True
    created_at: datetime = Field(default_factory=_now)


class XrayClient(SQLModel, table=True):
    """An Xray client, addressed by its email tag.

    There is no column for its UUID on purpose: the link is shown once, and a
    lost one is reissued, never recovered.
    """

    __tablename__ = "xray_client"

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True, unique=True)
    inbound_id: int = Field(foreign_key="inbound.id", index=True)
    email: str = Field(index=True, unique=True)
    flow: str | None = None
    enabled: bool = True
    created_at: datetime = Field(default_factory=_now)


class PeerCounter(SQLModel, table=True):
    """The last raw counters of one protocol of a profile, to take deltas from.

    rx is what the device received and tx what it sent, whatever the protocol.
    """

    __tablename__ = "peer_counter"

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    protocol: str
    rx: int = 0
    tx: int = 0
    seen_at: datetime | None = None
    source: str | None = None
    sampled_at: datetime = Field(default_factory=_now)


class TrafficHour(SQLModel, table=True):
    """Traffic of one protocol of a profile within one hour."""

    __tablename__ = "traffic_hour"

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    protocol: str
    hour: datetime = Field(index=True)
    rx: int = 0
    tx: int = 0


class ProfileSession(SQLModel, table=True):
    """A stretch of time a profile was connected over one protocol."""

    __tablename__ = "profile_session"

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    protocol: str
    started_at: datetime = Field(index=True)
    ended_at: datetime | None = None
    last_seen_at: datetime
    source: str | None = None
    rx: int = 0
    tx: int = 0


class ReleasedIp(SQLModel, table=True):
    """An address a deleted peer used to hold.

    Kept so it is not handed out again straight away: a client config that is
    still in a pocket somewhere would otherwise collide with a new profile.
    """

    __tablename__ = "released_ip"

    id: int | None = Field(default=None, primary_key=True)
    interface_id: int = Field(foreign_key="interface.id", index=True)
    address: str = Field(index=True)
    released_at: datetime = Field(default_factory=_now)
