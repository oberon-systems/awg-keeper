"""What the API accepts and what it answers with."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    """The pre-set credentials, as the sign-in form sends them."""

    model_config = ConfigDict(extra="forbid")

    user: str
    password: str


class Identity(BaseModel):
    """Who the caller is, and the token their writes must echo."""

    model_config = ConfigDict(extra="forbid")

    user: str
    csrf_token: str | None = None


class PeerRead(BaseModel):
    """A peer as the panel knows it. No private key exists here to leak."""

    model_config = ConfigDict(extra="forbid")

    public_key: str
    assigned_ip: str
    allowed_ips: str
    interface_id: int
    interface: str
    enabled: bool


class XrayClientRead(BaseModel):
    """An Xray client as the panel knows it. No UUID exists here to leak."""

    model_config = ConfigDict(extra="forbid")

    inbound_id: int
    inbound: str
    email: str
    flow: str | None = None
    enabled: bool


class ProfileRead(BaseModel):
    """A profile, the agent it lives on, and what it owns."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    note: str | None = None
    enabled: bool
    created_at: datetime
    node: str | None = None
    peer: PeerRead | None = None
    xray: XrayClientRead | None = None


class AwgRequest(BaseModel):
    """The AmneziaWG half of a new profile. The key was generated in the browser."""

    model_config = ConfigDict(extra="forbid")

    interface_id: int
    public_key: str


class XrayRequest(BaseModel):
    """The Xray half of a new profile. The UUID was generated in the browser."""

    model_config = ConfigDict(extra="forbid")

    inbound_id: int
    id: UUID


class ProfileCreate(BaseModel):
    """Adding a profile with an AmneziaWG peer, an Xray client, or both."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    note: str | None = None
    awg: AwgRequest | None = None
    xray: XrayRequest | None = None

    @model_validator(mode="after")
    def _something(self) -> ProfileCreate:
        if self.awg is None and self.xray is None:
            raise ValueError("a profile needs AmneziaWG, Xray or both")
        return self


class ProfileIssued(BaseModel):
    """What the browser needs to finish a profile it has just created.

    The template carries every field but the private key, which the browser
    holds and injects locally; the link carries the UUID only because the
    browser sent it. This is the only moment either can be rendered.
    """

    model_config = ConfigDict(extra="forbid")

    profile: ProfileRead
    config_template: str | None = None
    amnezia_template: str | None = None
    link: str | None = None


class ProfileUpdate(BaseModel):
    """Turning a profile's AmneziaWG peer off and on again."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool


class AwgReissue(BaseModel):
    """The new public key of a peer. Its private half stays in the browser."""

    model_config = ConfigDict(extra="forbid")

    public_key: str


class XrayReissue(BaseModel):
    """The new UUID of an Xray client, generated in the browser."""

    model_config = ConfigDict(extra="forbid")

    id: UUID


class ProfileReissue(BaseModel):
    """New keys for every half a profile owns, keeping its name and address."""

    model_config = ConfigDict(extra="forbid")

    awg: AwgReissue | None = None
    xray: XrayReissue | None = None


class InboundRead(BaseModel):
    """An enabled inbound, as the create form needs to offer it."""

    model_config = ConfigDict(extra="forbid")

    id: int
    node_id: int
    tag: str
    port: int
    network: str
    security: str
    endpoint_host: str


class Bucket(BaseModel):
    """Traffic within one hour or one day."""

    model_config = ConfigDict(extra="forbid")

    start: datetime
    rx: int = 0
    tx: int = 0


class ProtocolStats(BaseModel):
    """Traffic of one protocol of a profile within the period."""

    model_config = ConfigDict(extra="forbid")

    protocol: str
    key: str
    rx: int = 0
    tx: int = 0
    last_seen_at: datetime | None = None


class SessionRead(BaseModel):
    """One stretch of time a profile was connected."""

    model_config = ConfigDict(extra="forbid")

    started_at: datetime
    ended_at: datetime | None = None
    protocol: str
    source: str | None = None
    traffic: int = 0


class ProfileStats(BaseModel):
    """What the stats modal shows. rx is received by the device, tx sent by it."""

    model_config = ConfigDict(extra="forbid")

    period: str
    online: bool = False
    last_seen_at: datetime | None = None
    last_source: str | None = None
    rx: int = 0
    tx: int = 0
    connected_seconds: int = 0
    session_count: int = 0
    buckets: list[Bucket] = []
    protocols: list[ProtocolStats] = []
    sessions: list[SessionRead] = []


class OwnStats(BaseModel):
    """The public stats page: the caller's profile, found by its tunnel address."""

    model_config = ConfigDict(extra="forbid")

    source: str
    name: str | None = None
    node: str | None = None
    address: str | None = None
    stats: ProfileStats | None = None


class InterfaceRead(BaseModel):
    """An interface, as the create form needs to offer it."""

    model_config = ConfigDict(extra="forbid")

    id: int
    node_id: int
    name: str
    address: str
    pool: str
    listen_port: int
    endpoint_host: str
    client_allowed_ips: str
    obfuscation: dict[str, Any] = {}


class NodeRead(BaseModel):
    """A node and what the panel last heard from it."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    endpoint: str
    status: str
    last_seen: datetime | None = None


class AgentInterface(BaseModel):
    """An interface: what the agent last reported, and what the operator set."""

    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    name: str
    present: bool
    peers: int = 0
    public_key: str | None = None
    listen_port: int = 0
    error: str | None = None
    enabled: bool = False
    address: str | None = None
    pool: str | None = None
    endpoint_host: str | None = None
    label: str | None = None
    dns: str | None = None
    mtu: int | None = None
    client_allowed_ips: str | None = None
    keepalive: int | None = None
    obfuscation: dict[str, Any] = {}
    addresses: list[str] = []
    missing: list[str] = []


class AgentInbound(BaseModel):
    """An Xray inbound: what the agent last reported, and what the operator set."""

    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    tag: str
    present: bool
    clients: int = 0
    protocol: str = ""
    port: int = 0
    network: str = "tcp"
    security: str = "none"
    server_names: list[str] = []
    short_ids: list[str] = []
    public_key: str | None = None
    enabled: bool = False
    endpoint_host: str | None = None
    flow: str | None = None
    fingerprint: str | None = None
    short_id: str | None = None
    label: str | None = None
    missing: list[str] = []


class AgentRead(BaseModel):
    """A node and its last healthcheck."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    endpoint: str
    # False for a node left in the database after leaving AWG_PANEL_AGENTS.
    configured: bool = True
    status: str
    last_seen: datetime | None = None
    checked_at: datetime | None = None
    latency_ms: float | None = None
    version: str | None = None
    awg: str | None = None
    xray: str | None = None
    interfaces: list[AgentInterface] = []
    inbounds: list[AgentInbound] = []
    error: str | None = None


class CheckRead(BaseModel):
    """One entry of an agent's healthcheck log."""

    model_config = ConfigDict(extra="forbid")

    id: int
    checked_at: datetime
    status: str
    latency_ms: float | None = None
    error: str | None = None
    version: str | None = None
    awg: str | None = None
    xray: str | None = None
    interfaces: list[dict[str, Any]] = []


class InterfaceUpdate(BaseModel):
    """What the operator sets on a discovered interface. Absent keys are kept."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    address: str | None = None
    pool: str | None = None
    endpoint_host: str | None = None
    label: str | None = None
    dns: str | None = None
    mtu: int | None = Field(default=None, ge=576, le=65535)
    client_allowed_ips: str | None = None
    keepalive: int | None = Field(default=None, ge=0, le=65535)


class InboundUpdate(BaseModel):
    """What the operator sets on a discovered inbound. Absent keys are kept."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    endpoint_host: str | None = None
    flow: str | None = None
    fingerprint: str | None = None
    short_id: str | None = None
    label: str | None = None


class Drift(BaseModel):
    """What the panel wants against what the node actually has."""

    model_config = ConfigDict(extra="forbid")

    node_id: int
    reachable: bool
    detail: str | None = None
    missing_on_node: list[str] = []
    unknown_to_panel: list[str] = []
