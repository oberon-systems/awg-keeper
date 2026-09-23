"""What the API accepts and what it answers with.

The wire names follow awg and Xray rather than Python: a reader comparing a
response against `awg show dump` or a config.json should not have to translate.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Peer(BaseModel):
    """One AmneziaWG peer, as `awg show <iface> dump` reports it."""

    model_config = ConfigDict(extra="forbid")

    public_key: str
    allowed_ips: list[str] = []
    endpoint: str | None = None
    # Unix seconds; zero means the peer has never completed a handshake.
    latest_handshake: int = 0
    transfer_rx: int = 0
    transfer_tx: int = 0
    persistent_keepalive: int | None = None


class PeerCreate(BaseModel):
    """What adding a peer needs. The private key is the client's business."""

    model_config = ConfigDict(extra="forbid")

    public_key: str
    allowed_ips: list[str] = Field(min_length=1)
    persistent_keepalive: int | None = Field(default=None, ge=0, le=65535)


class Interface(BaseModel):
    """An interface and its peers. The private key is never carried."""

    model_config = ConfigDict(extra="forbid")

    name: str
    public_key: str | None = None
    listen_port: int = 0
    fwmark: str | None = None
    peers: list[Peer] = []


class XrayUser(BaseModel):
    """One Xray client, addressed by its email tag."""

    model_config = ConfigDict(extra="forbid")

    email: str
    id: str
    flow: str | None = None
    level: int = 0


class XrayUserCreate(BaseModel):
    """What adding an Xray client needs."""

    model_config = ConfigDict(extra="forbid")

    email: str
    id: str
    flow: str | None = None
    level: int = Field(default=0, ge=0)


class XrayTransport(BaseModel):
    """What a client link needs from an inbound; never the Reality private key."""

    model_config = ConfigDict(extra="forbid")

    tag: str
    protocol: str = ""
    listen: str | None = None
    port: int = 0
    network: str = "tcp"
    security: str = "none"
    server_names: list[str] = []
    short_ids: list[str] = []
    public_key: str | None = None


class XrayInbound(XrayTransport):
    """An inbound and the clients config.json holds for it."""

    users: list[XrayUser] = []


class InboundHealth(XrayTransport):
    """An inbound as the healthcheck reports it: the transport and a client count."""

    clients: int = 0


class XrayUserStats(BaseModel):
    """What the stats service counted for one client since Xray started."""

    model_config = ConfigDict(extra="forbid")

    email: str
    uplink: int = 0
    downlink: int = 0
    online_ips: list[str] = []


class XrayStats(BaseModel):
    """Per-client counters, or enabled false when config.json turns them off."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    users: list[XrayUserStats] = []


class State(BaseModel):
    """Actual state, which the Panel compares against what it wanted."""

    model_config = ConfigDict(extra="forbid")

    interfaces: list[Interface] = []
    inbounds: list[XrayInbound] = []


class Health(BaseModel):
    """Liveness, and the versions of the tools this agent drives."""

    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    version: str
    awg: str | None = None
    xray: str | None = None


class InterfaceHealth(BaseModel):
    """An interface as awg shows it, or the reason it could not."""

    model_config = ConfigDict(extra="forbid")

    name: str
    present: bool
    peers: int = 0
    public_key: str | None = None
    listen_port: int = 0
    # awg field name to value, only the ones that differ from plain WireGuard.
    obfuscation: dict[str, str] = {}
    addresses: list[str] = []
    error: str | None = None


class Status(Health):
    """Health, and what the host shows for the interfaces this agent drives."""

    interfaces: list[InterfaceHealth] = []
    inbounds: list[InboundHealth] = []
    error: str | None = None
