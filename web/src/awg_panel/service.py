"""What happens when a profile is created or deleted.

The panel writes its own row first and pushes to the node second, so a node
that refuses leaves nothing behind: the transaction is rolled back and the
address goes back in the pool.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from ipaddress import ip_interface, ip_network
from typing import Any

from sqlalchemy import Engine, delete
from sqlmodel import Session, col, select

from awg_panel import agent, clientconf, pool
from awg_panel.config import Settings
from awg_panel.models import AgentCheck, AwgPeer, Interface, Node, Profile
from awg_panel.schemas import (
    AgentInterface,
    AgentRead,
    CheckRead,
    InterfaceUpdate,
    PeerRead,
    ProfileCreate,
    ProfileIssued,
    ProfileRead,
)

LOG = logging.getLogger(__name__)


class UnknownProfile(LookupError):
    """No profile with that id."""


class UnknownInterface(LookupError):
    """No interface with that id."""


class UnknownNode(LookupError):
    """No node with that id."""


class InterfaceNotReady(ValueError):
    """An interface that is disabled, or cannot be enabled as configured."""


class DuplicateProfile(ValueError):
    """A profile with that name, or a peer with that key, already exists."""


def _read(profile: Profile, peer: AwgPeer | None) -> ProfileRead:
    return ProfileRead(
        id=int(profile.id or 0),
        name=profile.name,
        note=profile.note,
        enabled=profile.enabled,
        created_at=profile.created_at,
        peer=None
        if peer is None
        else PeerRead(
            public_key=peer.public_key,
            assigned_ip=peer.assigned_ip,
            allowed_ips=peer.allowed_ips,
            interface_id=peer.interface_id,
            enabled=peer.enabled,
        ),
    )


def _peer_of(session: Session, profile: Profile) -> AwgPeer | None:
    return session.exec(select(AwgPeer).where(AwgPeer.profile_id == profile.id)).first()


def node_of(session: Session, node_id: int) -> Node:
    """One node, or UnknownNode."""
    node = session.get(Node, node_id)
    if node is None:
        raise UnknownNode(str(node_id))
    return node


def list_profiles(session: Session) -> list[ProfileRead]:
    """Every profile, with its peer."""
    profiles = session.exec(select(Profile).order_by(Profile.name)).all()
    return [_read(profile, _peer_of(session, profile)) for profile in profiles]


def get_profile(session: Session, profile_id: int) -> ProfileRead:
    """One profile, or UnknownProfile."""
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise UnknownProfile(str(profile_id))
    return _read(profile, _peer_of(session, profile))


def create_profile(
    session: Session,
    settings: Settings,
    body: ProfileCreate,
) -> ProfileIssued:
    """Add a profile, allocate an address, push the peer, render the config."""
    interface = session.get(Interface, body.interface_id)
    if interface is None:
        raise UnknownInterface(str(body.interface_id))
    if not interface.enabled:
        raise InterfaceNotReady(f"interface {interface.name} is not enabled")
    node = node_of(session, interface.node_id)

    taken = session.exec(select(Profile).where(Profile.name == body.name)).first()
    if taken is not None:
        raise DuplicateProfile(body.name)

    existing = session.exec(
        select(AwgPeer).where(AwgPeer.public_key == body.public_key)
    ).first()
    if existing is not None:
        raise DuplicateProfile(body.public_key)

    profile = Profile(name=body.name, note=body.note)
    session.add(profile)
    session.flush()

    address = pool.allocate(session, interface)
    peer = AwgPeer(
        profile_id=int(profile.id or 0),
        interface_id=int(interface.id or 0),
        public_key=body.public_key,
        assigned_ip=address,
        allowed_ips=interface.client_allowed_ips,
    )
    session.add(peer)
    session.flush()

    try:
        agent.add_peer(
            settings,
            node,
            interface.name,
            peer.public_key,
            [peer.assigned_ip],
            interface.keepalive,
        )
    except agent.AgentError:
        session.rollback()
        raise

    session.commit()
    session.refresh(profile)
    session.refresh(peer)
    return ProfileIssued(
        profile=_read(profile, peer),
        config_template=clientconf.render(interface, peer),
    )


def delete_profile(session: Session, settings: Settings, profile_id: int) -> None:
    """Remove the peer from the node, then the rows, then quarantine the address."""
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise UnknownProfile(str(profile_id))

    peer = _peer_of(session, profile)
    if peer is not None:
        interface = session.get(Interface, peer.interface_id)
        if interface is not None:
            node = node_of(session, interface.node_id)
            agent.remove_peer(settings, node, interface.name, peer.public_key)
        pool.release(session, peer)
        session.delete(peer)

    session.delete(profile)
    session.commit()


OBFUSCATION_NAMES = {
    "jc": "Jc",
    "jmin": "Jmin",
    "jmax": "Jmax",
    "s1": "S1",
    "s2": "S2",
    "s3": "S3",
    "s4": "S4",
    "h1": "H1",
    "h2": "H2",
    "h3": "H3",
    "h4": "H4",
    "i1": "I1",
    "i2": "I2",
    "i3": "I3",
    "i4": "I4",
    "i5": "I5",
}
REQUIRED_TO_ENABLE = ("address", "pool", "endpoint_host")


def _utc(moment: datetime | None) -> datetime | None:
    # SQLite hands datetimes back naive; they were written in UTC.
    if moment is None or moment.tzinfo is not None:
        return moment
    return moment.replace(tzinfo=UTC)


def register_agents(session: Session, settings: Settings) -> None:
    """Make the node table match AWG_PANEL_AGENTS, and say what it holds."""
    known = {row.name: row for row in session.exec(select(Node)).all()}
    for name, url in settings.agents.items():
        row = known.get(name)
        if row is None:
            session.add(Node(name=name, endpoint=url))
            LOG.info("agent %s at %s registered", name, url)
        elif row.endpoint != url:
            LOG.info("agent %s moved from %s to %s", name, row.endpoint, url)
            row.endpoint = url
            session.add(row)
        else:
            LOG.info("agent %s at %s", name, url)

    for name in sorted(known.keys() - settings.agents.keys()):
        LOG.warning("agent %s is not in AWG_PANEL_AGENTS and is not probed", name)
    if not settings.agents:
        LOG.error("AWG_PANEL_AGENTS is empty: no agent will ever be probed")
    session.commit()


def _last_check(session: Session, node: Node) -> AgentCheck | None:
    query = (
        select(AgentCheck)
        .where(AgentCheck.node_id == node.id)
        .order_by(col(AgentCheck.checked_at).desc(), col(AgentCheck.id).desc())
    )
    return session.exec(query).first()


def _obfuscation(reported: dict[str, str]) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for field, value in reported.items():
        name = OBFUSCATION_NAMES.get(field)
        if name is not None:
            found[name] = int(value) if value.isdigit() else value
    return found


def _discover(session: Session, node: Node, reported: list[dict[str, Any]]) -> None:
    rows = {
        row.name: row
        for row in session.exec(select(Interface).where(Interface.node_id == node.id))
    }
    for item in reported:
        # An agent before 0.3.0 reports no key, and a row without one is useless.
        if not item.get("present") or not item.get("public_key"):
            continue
        row = rows.get(item["name"])
        if row is None:
            row = Interface(
                node_id=int(node.id or 0),
                name=item["name"],
                listen_port=int(item.get("listen_port") or 0),
                server_public_key=item["public_key"],
            )
            LOG.info(
                "agent %s: interface %s discovered, disabled until configured",
                node.name,
                row.name,
            )
        elif row.server_public_key != item["public_key"] or row.listen_port != item.get(
            "listen_port"
        ):
            LOG.warning(
                "agent %s: interface %s changed key or port; issued profiles are stale",
                node.name,
                row.name,
            )
        row.server_public_key = item["public_key"]
        row.listen_port = int(item.get("listen_port") or 0)
        row.obfuscation = _obfuscation(item.get("obfuscation") or {})
        session.add(row)


def _describe_interfaces(check: AgentCheck) -> str:
    parts = []
    for item in check.interfaces:
        if item.get("error"):
            parts.append(f"{item['name']} failing: {item['error']}")
        elif item.get("present"):
            parts.append(f"{item['name']} present")
        else:
            parts.append(f"{item['name']} absent")
    return ", ".join(parts) or "no interfaces"


def _log_check(
    node: Node,
    previous: AgentCheck | None,
    check: AgentCheck,
    announce: bool,
) -> None:
    interfaces = _describe_interfaces(check)
    changed = (
        announce
        or previous is None
        or previous.status != check.status
        or previous.error != check.error
        or _describe_interfaces(previous) != interfaces
    )
    if not changed:
        return

    if check.status == "down":
        LOG.error("agent %s down: %s", node.name, check.error)
        return
    level = logging.INFO if check.status == "up" else logging.WARNING
    LOG.log(
        level,
        "agent %s %s in %.0fms: agent %s, %s, %s; %s%s",
        node.name,
        check.status,
        check.latency_ms or 0,
        check.version,
        check.awg or "no awg",
        check.xray or "no xray",
        interfaces,
        f"; {check.error}" if check.error else "",
    )


def _probe(
    session: Session,
    settings: Settings,
    node: Node,
    announce: bool,
) -> AgentCheck:
    previous = _last_check(session, node)
    started = time.monotonic()
    try:
        answer = agent.status(settings, node)
    except agent.AgentError as exc:
        check = AgentCheck(
            node_id=int(node.id or 0),
            status="down",
            latency_ms=(time.monotonic() - started) * 1000,
            error=exc.reason,
        )
    else:
        interfaces = list(answer.get("interfaces") or [])
        failing = answer.get("error") or any(item.get("error") for item in interfaces)
        check = AgentCheck(
            node_id=int(node.id or 0),
            status="degraded" if failing else "up",
            latency_ms=(time.monotonic() - started) * 1000,
            error=answer.get("error"),
            version=answer.get("version"),
            awg=answer.get("awg"),
            xray=answer.get("xray"),
            interfaces=interfaces,
        )
        node.last_seen = check.checked_at
        _discover(session, node, interfaces)

    _log_check(node, previous, check, announce)
    node.status = check.status
    session.add(node)
    session.add(check)
    return check


def probe_agents(
    session: Session,
    settings: Settings,
    announce: bool = False,
) -> list[AgentRead]:
    """Check every configured agent once, record it, and prune the old checks."""
    nodes = session.exec(select(Node).order_by(Node.name)).all()
    for node in nodes:
        if node.name in settings.agents:
            _probe(session, settings, node, announce)

    horizon = datetime.now(UTC) - timedelta(days=settings.check_retention)
    session.exec(delete(AgentCheck).where(col(AgentCheck.checked_at) < horizon))
    session.commit()
    return list_agents(session, settings)


def probe_all(engine: Engine, settings: Settings, announce: bool = False) -> None:
    """One round of the background healthcheck. Never raises: the loop must live."""
    try:
        with Session(engine) as session:
            probe_agents(session, settings, announce)
    except Exception:
        LOG.exception("healthcheck round failed")


def _agent_interfaces(
    session: Session,
    node: Node,
    last: AgentCheck | None,
) -> list[AgentInterface]:
    rows = {
        row.name: row
        for row in session.exec(select(Interface).where(Interface.node_id == node.id))
    }
    reported = {item["name"]: item for item in (last.interfaces if last else [])}
    names = list(reported) + sorted(rows.keys() - reported.keys())

    found = []
    for name in names:
        item = reported.get(name)
        row = rows.get(name)
        error = None
        if item is not None:
            error = item.get("error")
        elif last is not None and last.status != "down":
            error = "not reported by the agent"
        found.append(
            AgentInterface(
                id=row.id if row else None,
                name=name,
                present=bool(item and item.get("present")),
                peers=int(item.get("peers", 0)) if item else 0,
                public_key=(item or {}).get("public_key")
                or (row.server_public_key if row else None),
                listen_port=(item or {}).get("listen_port")
                or (row.listen_port if row else 0),
                error=error,
                enabled=row.enabled if row else False,
                address=row.address if row else None,
                pool=row.pool if row else None,
                endpoint_host=row.endpoint_host if row else None,
                dns=row.dns if row else None,
                mtu=row.mtu if row else None,
                client_allowed_ips=row.client_allowed_ips if row else None,
                keepalive=row.keepalive if row else None,
                obfuscation=row.obfuscation if row else {},
            )
        )
    return found


def list_agents(session: Session, settings: Settings) -> list[AgentRead]:
    """Every node with its last healthcheck, as recorded; nothing is probed."""
    found = []
    for node in session.exec(select(Node).order_by(Node.name)).all():
        last = _last_check(session, node)
        found.append(
            AgentRead(
                id=int(node.id or 0),
                name=node.name,
                endpoint=node.endpoint,
                configured=node.name in settings.agents,
                status=node.status,
                last_seen=_utc(node.last_seen),
                checked_at=_utc(last.checked_at) if last else None,
                latency_ms=last.latency_ms if last else None,
                version=last.version if last else None,
                awg=last.awg if last else None,
                xray=last.xray if last else None,
                interfaces=_agent_interfaces(session, node, last),
                error=last.error if last else None,
            )
        )
    return found


def list_checks(session: Session, node_id: int, limit: int) -> list[CheckRead]:
    """Return the newest checks of one agent, newest first."""
    node = node_of(session, node_id)
    query = (
        select(AgentCheck)
        .where(AgentCheck.node_id == node.id)
        .order_by(col(AgentCheck.checked_at).desc(), col(AgentCheck.id).desc())
        .limit(limit)
    )
    return [
        CheckRead(
            id=int(row.id or 0),
            checked_at=_utc(row.checked_at) or row.checked_at,
            status=row.status,
            latency_ms=row.latency_ms,
            error=row.error,
            version=row.version,
            awg=row.awg,
            xray=row.xray,
            interfaces=row.interfaces or [],
        )
        for row in session.exec(query).all()
    ]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def update_interface(
    session: Session,
    settings: Settings,
    interface_id: int,
    body: InterfaceUpdate,
) -> AgentRead:
    """Apply what the operator set, refusing an enabled interface that cannot issue."""
    row = session.get(Interface, interface_id)
    if row is None:
        raise UnknownInterface(str(interface_id))
    node = node_of(session, row.node_id)

    for field in body.model_fields_set - {"enabled"}:
        value = getattr(body, field)
        if isinstance(value, str) or value is None:
            value = _clean(value)
        if field == "client_allowed_ips" and value is None:
            value = "0.0.0.0/0"
        setattr(row, field, value)
    if body.enabled is not None:
        row.enabled = body.enabled

    if row.pool:
        pool_network = ip_network(row.pool, strict=False)
        if row.address and ip_interface(row.address).ip not in pool_network:
            raise ValueError(f"address {row.address} is outside the pool {row.pool}")
    elif row.address:
        ip_interface(row.address)
    for item in row.client_allowed_ips.split(","):
        ip_network(item.strip(), strict=False)

    missing = [field for field in REQUIRED_TO_ENABLE if not getattr(row, field)]
    if row.enabled and missing:
        raise InterfaceNotReady(
            f"{row.name} cannot be enabled without {', '.join(missing)}"
        )

    session.add(row)
    session.commit()
    LOG.info(
        "agent %s: interface %s %s",
        node.name,
        row.name,
        "enabled" if row.enabled else "disabled",
    )
    return next(item for item in list_agents(session, settings) if item.id == node.id)
