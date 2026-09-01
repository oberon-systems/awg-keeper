"""What the API accepts and what it answers with."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    enabled: bool


class ProfileRead(BaseModel):
    """A profile and the peer it owns, if it owns one."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    note: str | None = None
    enabled: bool
    created_at: datetime
    peer: PeerRead | None = None


class ProfileCreate(BaseModel):
    """Adding a profile. The public key was generated in the browser."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    note: str | None = None
    interface_id: int
    public_key: str


class ProfileIssued(BaseModel):
    """What the browser needs to finish a profile it has just created.

    The template carries every field but the private key, which the browser
    holds and injects locally. This is the only moment it can be rendered.
    """

    model_config = ConfigDict(extra="forbid")

    profile: ProfileRead
    config_template: str


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


class Drift(BaseModel):
    """What the panel wants against what the node actually has."""

    model_config = ConfigDict(extra="forbid")

    node_id: int
    reachable: bool
    detail: str | None = None
    missing_on_node: list[str] = []
    unknown_to_panel: list[str] = []
