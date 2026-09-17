"""The routes. Every handler is a plain `def`.

Both the database driver and the agent client are synchronous, so an
`async def` here would block the event loop for every other request.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlmodel import Session, col, select

from awg_panel import __version__, agent, auth, db, service
from awg_panel.models import AwgPeer, Interface, Node
from awg_panel.schemas import (
    AgentRead,
    CheckRead,
    Drift,
    Identity,
    InterfaceRead,
    InterfaceUpdate,
    LoginRequest,
    NodeRead,
    ProfileCreate,
    ProfileIssued,
    ProfileRead,
)

LOG = logging.getLogger(__name__)


def session_of(request: Request) -> Iterator[Session]:
    """One database session per request."""
    yield from db.session_of(request.app.state.engine)


# No dependencies at all: the container healthcheck calls it before anyone
# has signed in, and it says nothing a stranger could use.
ping = APIRouter(prefix="/api/v1", tags=["public"])
public = APIRouter(
    prefix="/api/v1",
    tags=["auth"],
    dependencies=[Depends(auth.require_source)],
)
private = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(auth.require_source), Depends(auth.require_session)],
)

SessionDep = Annotated[Session, Depends(session_of)]
UserDep = Annotated[str, Depends(auth.require_session)]


@ping.get("/ping")
def alive() -> dict[str, str]:
    """Liveness only. Says nothing about the node or the database."""
    return {"status": "ok", "version": __version__}


@public.post("/auth/login")
def login(request: Request, response: Response, body: LoginRequest) -> Identity:
    """Sign in with the pre-set credentials and take a session cookie."""
    settings = auth.settings_of(request)
    auth.authenticate(settings, body.user, body.password)
    csrf = auth.open_session(settings, response, body.user)
    return Identity(user=body.user, csrf_token=csrf)


@public.post("/auth/logout", status_code=204)
def logout(response: Response) -> Response:
    """Drop the session. Valid without one, so a stale tab can still clear."""
    auth.close_session(response)
    return Response(status_code=204)


@private.get("/auth/me")
def me(user: UserDep) -> Identity:
    """Who the session says the caller is."""
    return Identity(user=user)


@private.get("/health")
def health(request: Request, session: SessionDep) -> dict[str, object]:
    """Report the panel, and every node as its last healthcheck left it."""
    agents = service.list_agents(session, auth.settings_of(request))
    return {"status": "ok", "version": __version__, "nodes": agents}


@private.get("/agents")
def list_agents(request: Request, session: SessionDep) -> list[AgentRead]:
    """Every agent and its last healthcheck. Probes nothing."""
    return service.list_agents(session, auth.settings_of(request))


@private.post("/agents/probe")
def probe_agents(request: Request, session: SessionDep) -> list[AgentRead]:
    """Healthcheck every agent now, instead of waiting for the next round."""
    return service.probe_agents(session, auth.settings_of(request))


@private.get("/agents/{node_id}/checks")
def list_checks(
    node_id: int,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[CheckRead]:
    """Return the healthcheck log of one agent, newest first."""
    return service.list_checks(session, node_id, limit)


@private.get("/profiles")
def list_profiles(session: SessionDep) -> list[ProfileRead]:
    """Every profile the panel knows."""
    return service.list_profiles(session)


@private.post("/profiles", status_code=201)
def create_profile(
    request: Request,
    body: ProfileCreate,
    session: SessionDep,
) -> ProfileIssued:
    """Add a profile, push its peer to the node, and render its config once."""
    return service.create_profile(session, auth.settings_of(request), body)


@private.get("/profiles/{profile_id}")
def show_profile(
    profile_id: int,
    session: SessionDep,
) -> ProfileRead:
    """One profile."""
    return service.get_profile(session, profile_id)


@private.delete("/profiles/{profile_id}", status_code=204)
def remove_profile(
    request: Request,
    profile_id: int,
    session: SessionDep,
) -> Response:
    """Remove a profile and its peer, and quarantine the address it held."""
    service.delete_profile(session, auth.settings_of(request), profile_id)
    return Response(status_code=204)


@private.get("/interfaces")
def list_interfaces(session: SessionDep) -> list[InterfaceRead]:
    """List the enabled interfaces, the ones a profile can be issued against."""
    query = select(Interface).where(col(Interface.enabled)).order_by(Interface.name)
    rows = session.exec(query).all()
    if not rows:
        LOG.warning("no enabled interface; enable one on the status page")
    return [
        InterfaceRead(
            id=int(row.id or 0),
            node_id=row.node_id,
            name=row.name,
            address=row.address or "",
            pool=row.pool or "",
            listen_port=row.listen_port,
            endpoint_host=row.endpoint_host or "",
            client_allowed_ips=row.client_allowed_ips,
            obfuscation=row.obfuscation,
        )
        for row in rows
    ]


@private.patch("/interfaces/{interface_id}")
def update_interface(
    request: Request,
    interface_id: int,
    body: InterfaceUpdate,
    session: SessionDep,
) -> AgentRead:
    """Configure a discovered interface and enable or disable it."""
    return service.update_interface(
        session, auth.settings_of(request), interface_id, body
    )


@private.get("/nodes")
def list_nodes(session: SessionDep) -> list[NodeRead]:
    """List the nodes. v1 has exactly one."""
    rows = session.exec(select(Node).order_by(Node.name)).all()
    return [
        NodeRead(
            id=int(row.id or 0),
            name=row.name,
            endpoint=row.endpoint,
            status=row.status,
            last_seen=row.last_seen,
        )
        for row in rows
    ]


@private.get("/nodes/{node_id}/drift")
def drift(
    request: Request,
    node_id: int,
    session: SessionDep,
) -> Drift:
    """Compare what the panel wants against what the node has."""
    settings = auth.settings_of(request)
    node = service.node_of(session, node_id)
    try:
        actual = agent.state(settings, node)
    except agent.AgentError as exc:
        LOG.warning("drift of %s: %s", node.name, exc.reason)
        return Drift(node_id=node_id, reachable=False, detail=exc.reason)

    on_node: set[str] = set()
    for entry in actual.get("interfaces", []):
        for peer in entry.get("peers", []):
            on_node.add(str(peer.get("public_key", "")))

    interfaces = session.exec(
        select(Interface).where(Interface.node_id == node_id)
    ).all()
    wanted = {
        peer.public_key
        for interface in interfaces
        for peer in _peers_of(session, int(interface.id or 0))
    }

    return Drift(
        node_id=node_id,
        reachable=True,
        missing_on_node=sorted(wanted - on_node),
        unknown_to_panel=sorted(on_node - wanted),
    )


def _peers_of(session: Session, interface_id: int) -> list[AwgPeer]:
    query = select(AwgPeer).where(AwgPeer.interface_id == interface_id)
    return list(session.exec(query).all())
