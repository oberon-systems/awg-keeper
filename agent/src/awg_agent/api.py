"""The routes. Every handler is a plain `def`.

subprocess is synchronous, so an `async def` here would block the event loop
for every other request in flight.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response

from awg_agent import __version__, awg, xray
from awg_agent.auth import require_source, require_token, settings_of
from awg_agent.commands import CommandError
from awg_agent.models import (
    Health,
    InboundHealth,
    Interface,
    Peer,
    PeerCreate,
    State,
    Status,
    XrayInbound,
    XrayStats,
    XrayUser,
    XrayUserCreate,
)

LOG = logging.getLogger(__name__)

# A public key holds "+" and "/", and the ASGI server decodes the path
# before routing, so the key is matched with the path converter.
public = APIRouter(prefix="/v1", tags=["public"])
private = APIRouter(
    prefix="/v1",
    dependencies=[Depends(require_token), Depends(require_source)],
)


@public.get("/health")
def health(request: Request) -> Health:
    """Liveness, and the versions of the tools this agent drives."""
    settings = settings_of(request)
    return Health(
        version=__version__,
        awg=awg.version(settings),
        xray=xray.version(settings),
    )


@private.get("/state")
def state(request: Request) -> State:
    """Actual state: what the host has, for the Panel to compare against."""
    settings = settings_of(request)
    found: list[Interface] = [
        awg.show(settings, name) for name in awg.interfaces(settings)
    ]

    inbounds: list[XrayInbound] = []
    try:
        inbounds = xray.inbounds(settings)
    except (CommandError, OSError) as exc:
        # A host with no Xray is a supported deployment, not a failed request.
        LOG.info("no xray state: %s", exc)

    LOG.info(
        "state: %d interfaces, %d peers, %d inbounds",
        len(found),
        sum(len(item.peers) for item in found),
        len(inbounds),
    )
    return State(interfaces=found, inbounds=inbounds)


@private.get("/status")
def status(request: Request) -> Status:
    """Health, and what awg shows per interface; a failure is reported, not raised."""
    settings = settings_of(request)
    interfaces, error = awg.probe(settings)
    request.app.state.interfaces_seen = awg.log_probe(
        interfaces, error, request.app.state.interfaces_seen
    )
    inbounds: list[InboundHealth] = []
    try:
        inbounds = xray.health(settings)
    except CommandError as exc:
        LOG.warning("xray inbounds unavailable: %s", exc)
    return Status(
        version=__version__,
        awg=awg.version(settings),
        xray=xray.version(settings),
        interfaces=interfaces,
        inbounds=inbounds,
        error=error,
    )


@private.get("/awg/{iface}/peers")
def list_peers(request: Request, iface: str) -> list[Peer]:
    """Every peer configured on the interface."""
    return awg.list_peers(settings_of(request), iface)


@private.post("/awg/{iface}/peers", status_code=201)
def add_peer(request: Request, iface: str, body: PeerCreate) -> Peer:
    """Add one peer and persist the interface config."""
    return awg.add_peer(
        settings_of(request),
        iface,
        body.public_key,
        body.allowed_ips,
        body.persistent_keepalive,
    )


@private.get("/awg/{iface}/peers/{public_key:path}")
def show_peer(request: Request, iface: str, public_key: str) -> Peer:
    """One peer, by public key."""
    return awg.show_peer(settings_of(request), iface, public_key)


@private.delete("/awg/{iface}/peers/{public_key:path}", status_code=204)
def remove_peer(request: Request, iface: str, public_key: str) -> Response:
    """Remove one peer and persist the interface config."""
    awg.remove_peer(settings_of(request), iface, public_key)
    return Response(status_code=204)


@private.get("/xray/stats")
def xray_stats(request: Request) -> XrayStats:
    """Traffic counters and online addresses per Xray client."""
    return xray.stats(settings_of(request))


@private.get("/xray/{inbound}/users")
def list_users(request: Request, inbound: str) -> list[XrayUser]:
    """Every client of the inbound."""
    return xray.list_users(settings_of(request), inbound)


@private.post("/xray/{inbound}/users", status_code=201)
def add_user(request: Request, inbound: str, body: XrayUserCreate) -> XrayUser:
    """Add one client to the running instance and to config.json."""
    return xray.add_user(
        settings_of(request),
        inbound,
        body.id,
        body.email,
        body.flow,
        body.level,
    )


@private.get("/xray/{inbound}/users/{email}")
def show_user(request: Request, inbound: str, email: str) -> XrayUser:
    """One client, by email tag."""
    return xray.show_user(settings_of(request), inbound, email)


@private.delete("/xray/{inbound}/users/{email}", status_code=204)
def remove_user(request: Request, inbound: str, email: str) -> Response:
    """Remove one client from the running instance and from config.json."""
    xray.remove_user(settings_of(request), inbound, email)
    return Response(status_code=204)
