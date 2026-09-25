"""What happens when a profile is created or deleted.

The panel writes its own row first and pushes to the node second, so a node
that refuses leaves nothing behind: the transaction is rolled back and the
address goes back in the pool.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from ipaddress import ip_interface, ip_network
from typing import Any

from sqlalchemy import Engine, delete
from sqlmodel import Session, col, select

from awg_panel import agent, amneziakey, clientconf, clientlink, pool, stats
from awg_panel.config import Settings
from awg_panel.models import (
    AgentCheck,
    AwgPeer,
    Inbound,
    Interface,
    Node,
    PeerCounter,
    Profile,
    ProfileSession,
    TrafficHour,
    XrayClient,
)
from awg_panel.schemas import (
    AgentInbound,
    AgentInterface,
    AgentRead,
    CheckRead,
    InboundUpdate,
    InterfaceUpdate,
    ObfuscationUpdate,
    PeerRead,
    ProfileCreate,
    ProfileEdit,
    ProfileIssued,
    ProfileRead,
    ProfileReissue,
    XrayClientRead,
)

LOG = logging.getLogger(__name__)


class UnknownProfile(LookupError):
    """No profile with that id."""


class UnknownInterface(LookupError):
    """No interface with that id."""


class UnknownNode(LookupError):
    """No node with that id."""


class UnknownInbound(LookupError):
    """No inbound with that id."""


class InboundNotReady(ValueError):
    """An inbound that cannot be enabled as configured."""


class InterfaceNotReady(ValueError):
    """An interface that is disabled, or cannot be enabled as configured."""


class DuplicateProfile(ValueError):
    """A profile with that name, or a peer with that key, already exists."""


# An email tag is what Xray addresses a client by, and the agent validates it.
EMAIL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]{0,63}$")


def _read(session: Session, profile: Profile) -> ProfileRead:
    peer = _peer_of(session, profile)
    client = _client_of(session, profile)
    interface = session.get(Interface, peer.interface_id) if peer else None
    inbound = session.get(Inbound, client.inbound_id) if client else None
    owner: Interface | Inbound | None = interface or inbound
    node = session.get(Node, owner.node_id) if owner else None
    stale = bool(
        peer
        and interface
        and peer.issued_digest
        and peer.issued_digest != _digest(interface, peer, profile)
    )
    return ProfileRead(
        id=int(profile.id or 0),
        name=profile.name,
        note=profile.note,
        dns=profile.dns,
        mtu=profile.mtu,
        enabled=profile.enabled,
        created_at=_utc(profile.created_at) or profile.created_at,
        node=node.name if node else None,
        peer=None
        if peer is None
        else PeerRead(
            public_key=peer.public_key,
            assigned_ip=peer.assigned_ip,
            allowed_ips=peer.allowed_ips,
            interface_id=peer.interface_id,
            interface=interface.name if interface else "",
            enabled=peer.enabled,
            reroll=stale,
        ),
        xray=None
        if client is None
        else XrayClientRead(
            inbound_id=client.inbound_id,
            inbound=inbound.tag if inbound else "",
            email=client.email,
            flow=client.flow,
            enabled=client.enabled,
        ),
    )


def _digest(interface: Interface, peer: AwgPeer, profile: Profile) -> str:
    rendered = clientconf.render(interface, peer, profile)
    return hashlib.sha256(rendered.encode()).hexdigest()


def backfill_digests(session: Session) -> None:
    """Take every config issued before digests were kept as matching the current one.

    Run at start, so an upgrade does not flag every profile for a reroll.
    """
    peers = session.exec(select(AwgPeer).where(col(AwgPeer.issued_digest).is_(None)))
    stamped = 0
    for peer in peers.all():
        interface = session.get(Interface, peer.interface_id)
        profile = session.get(Profile, peer.profile_id)
        if interface is not None and profile is not None:
            peer.issued_digest = _digest(interface, peer, profile)
            session.add(peer)
            stamped += 1
    if stamped:
        LOG.info("%d issued configs recorded as current", stamped)
    session.commit()


def _peer_of(session: Session, profile: Profile) -> AwgPeer | None:
    return session.exec(select(AwgPeer).where(AwgPeer.profile_id == profile.id)).first()


def _client_of(session: Session, profile: Profile) -> XrayClient | None:
    query = select(XrayClient).where(XrayClient.profile_id == profile.id)
    return session.exec(query).first()


def node_of(session: Session, node_id: int) -> Node:
    """One node, or UnknownNode."""
    node = session.get(Node, node_id)
    if node is None:
        raise UnknownNode(str(node_id))
    return node


def list_profiles(session: Session) -> list[ProfileRead]:
    """Every profile, with its peer and its Xray client."""
    profiles = session.exec(select(Profile).order_by(Profile.name)).all()
    return [_read(session, profile) for profile in profiles]


def get_profile(session: Session, profile_id: int) -> ProfileRead:
    """One profile, or UnknownProfile."""
    return _read(session, profile_of(session, profile_id))


def profile_of(session: Session, profile_id: int) -> Profile:
    """One profile row, or UnknownProfile."""
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise UnknownProfile(str(profile_id))
    return profile


def _issuable_interface(session: Session, interface_id: int) -> Interface:
    interface = session.get(Interface, interface_id)
    if interface is None:
        raise UnknownInterface(str(interface_id))
    if not interface.enabled:
        raise InterfaceNotReady(f"interface {interface.name} is not enabled")
    return interface


def _issuable_inbound(session: Session, inbound_id: int) -> Inbound:
    inbound = session.get(Inbound, inbound_id)
    if inbound is None:
        raise UnknownInbound(str(inbound_id))
    if not inbound.enabled:
        raise InboundNotReady(f"inbound {inbound.tag} is not enabled")
    return inbound


def create_profile(
    session: Session,
    settings: Settings,
    body: ProfileCreate,
) -> ProfileIssued:
    """Add a profile, push its peer and its Xray client, render them once."""
    interface: Interface | None = None
    inbound: Inbound | None = None
    if body.awg is not None:
        interface = _issuable_interface(session, body.awg.interface_id)
    if body.xray is not None:
        inbound = _issuable_inbound(session, body.xray.inbound_id)
    owner: Interface | Inbound | None = interface or inbound
    if owner is None:
        raise ValueError("a profile needs AmneziaWG, Xray or both")
    if interface and inbound and interface.node_id != inbound.node_id:
        raise ValueError("the interface and the inbound are on different agents")
    node = node_of(session, owner.node_id)

    taken = session.exec(select(Profile).where(Profile.name == body.name)).first()
    if taken is not None:
        raise DuplicateProfile(body.name)
    if inbound is not None:
        if not EMAIL.match(body.name):
            raise ValueError(
                f"{body.name!r} cannot be an Xray email tag: use letters, digits "
                "and . _ @ + -, starting with a letter or digit"
            )
        clash = select(XrayClient).where(XrayClient.email == body.name)
        if session.exec(clash).first() is not None:
            raise DuplicateProfile(body.name)
    if body.awg is not None:
        existing = session.exec(
            select(AwgPeer).where(AwgPeer.public_key == body.awg.public_key)
        ).first()
        if existing is not None:
            raise DuplicateProfile(body.awg.public_key)

    profile = Profile(name=body.name, note=body.note)
    session.add(profile)
    session.flush()

    peer = None
    if interface is not None and body.awg is not None:
        peer = AwgPeer(
            profile_id=int(profile.id or 0),
            interface_id=int(interface.id or 0),
            public_key=body.awg.public_key,
            assigned_ip=pool.allocate(session, interface),
            allowed_ips=interface.client_allowed_ips,
        )
        peer.issued_digest = _digest(interface, peer, profile)
        session.add(peer)
    client = None
    link = None
    if inbound is not None and body.xray is not None:
        client = XrayClient(
            profile_id=int(profile.id or 0),
            inbound_id=int(inbound.id or 0),
            email=body.name,
            flow=inbound.flow,
        )
        session.add(client)
        link = clientlink.render(inbound, str(body.xray.id), body.name)
    session.flush()

    try:
        if peer is not None and interface is not None:
            agent.add_peer(
                settings,
                node,
                interface.name,
                peer.public_key,
                [peer.assigned_ip],
                interface.keepalive,
            )
        if client is not None and inbound is not None and body.xray is not None:
            try:
                agent.add_user(
                    settings,
                    node,
                    inbound.tag,
                    str(body.xray.id),
                    client.email,
                    client.flow,
                )
            except agent.AgentError:
                if peer is not None and interface is not None:
                    agent.remove_peer(settings, node, interface.name, peer.public_key)
                raise
    except agent.AgentError:
        session.rollback()
        raise

    session.commit()
    session.refresh(profile)
    return _issued(session, profile, peer, link)


def _issued(
    session: Session,
    profile: Profile,
    peer: AwgPeer | None,
    link: str | None,
) -> ProfileIssued:
    interface = session.get(Interface, peer.interface_id) if peer else None
    if peer is None or interface is None:
        return ProfileIssued(profile=_read(session, profile), link=link)
    return ProfileIssued(
        profile=_read(session, profile),
        config_template=clientconf.render(interface, peer, profile),
        amnezia_template=amneziakey.render(interface, peer, profile.name, profile),
        link=link,
    )


def _interface_of(session: Session, peer: AwgPeer) -> Interface:
    interface = session.get(Interface, peer.interface_id)
    if interface is None:
        raise UnknownInterface(str(peer.interface_id))
    return interface


def set_profile_enabled(
    session: Session,
    settings: Settings,
    profile_id: int,
    enabled: bool,
) -> ProfileRead:
    """Take a profile's peer off the node or put it back; rows and stats stay."""
    profile = profile_of(session, profile_id)
    peer = _peer_of(session, profile)
    if peer is None:
        raise ValueError(f"{profile.name} has no AmneziaWG peer to turn on or off")

    if peer.enabled != enabled:
        interface = _interface_of(session, peer)
        node = node_of(session, interface.node_id)
        if enabled:
            agent.add_peer(
                settings,
                node,
                interface.name,
                peer.public_key,
                [peer.assigned_ip],
                interface.keepalive,
            )
        else:
            agent.remove_peer(settings, node, interface.name, peer.public_key)
    peer.enabled = enabled
    profile.enabled = enabled
    session.add(peer)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    LOG.info("profile %s %s", profile.name, "enabled" if enabled else "disabled")
    return _read(session, profile)


def reissue_profile(
    session: Session,
    settings: Settings,
    profile_id: int,
    body: ProfileReissue,
) -> ProfileIssued:
    """Replace the keys of a profile; its name, address and stats are kept."""
    profile = profile_of(session, profile_id)
    peer = _peer_of(session, profile)
    client = _client_of(session, profile)
    if (peer is None) != (body.awg is None) or (client is None) != (body.xray is None):
        raise ValueError(f"{profile.name} needs a new key for each half it owns")

    if peer is not None and body.awg is not None:
        existing = session.exec(
            select(AwgPeer).where(AwgPeer.public_key == body.awg.public_key)
        ).first()
        if existing is not None:
            raise DuplicateProfile(body.awg.public_key)
        if peer.enabled:
            interface = _interface_of(session, peer)
            node = node_of(session, interface.node_id)
            agent.remove_peer(settings, node, interface.name, peer.public_key)
            try:
                agent.add_peer(
                    settings,
                    node,
                    interface.name,
                    body.awg.public_key,
                    [peer.assigned_ip],
                    interface.keepalive,
                )
            except agent.AgentError:
                agent.add_peer(
                    settings,
                    node,
                    interface.name,
                    peer.public_key,
                    [peer.assigned_ip],
                    interface.keepalive,
                )
                raise
        peer.public_key = body.awg.public_key
        peer.issued_digest = _digest(_interface_of(session, peer), peer, profile)
        session.add(peer)

    link = None
    if client is not None and body.xray is not None:
        inbound = session.get(Inbound, client.inbound_id)
        if inbound is None:
            raise UnknownInbound(str(client.inbound_id))
        node = node_of(session, inbound.node_id)
        link = clientlink.render(inbound, str(body.xray.id), profile.name)
        # The old UUID is not kept anywhere, so a failed add is retried, not undone.
        agent.remove_user(settings, node, inbound.tag, client.email)
        agent.add_user(
            settings, node, inbound.tag, str(body.xray.id), client.email, client.flow
        )

    session.commit()
    session.refresh(profile)
    LOG.info("profile %s reissued", profile.name)
    return _issued(session, profile, peer, link)


def _name_for_xray(session: Session, name: str, own: XrayClient | None) -> None:
    if not EMAIL.match(name):
        raise ValueError(
            f"{name!r} cannot be an Xray email tag: use letters, digits "
            "and . _ @ + -, starting with a letter or digit"
        )
    clash = session.exec(select(XrayClient).where(XrayClient.email == name)).first()
    if clash is not None and clash is not own:
        raise DuplicateProfile(name)


def edit_profile(
    session: Session,
    settings: Settings,
    profile_id: int,
    body: ProfileEdit,
) -> ProfileIssued:
    """Rename, annotate and re-shape a profile; only an added half is rendered.

    The client config changes only on the device's next import, so an edit that
    changes what would be rendered leaves the peer flagged for a reroll.
    """
    profile = profile_of(session, profile_id)
    peer = _peer_of(session, profile)
    client = _client_of(session, profile)
    given = body.model_fields_set
    if body.awg is not None and peer is not None:
        raise ValueError(f"{profile.name} has an AmneziaWG peer already; reroll it")
    if body.xray is not None and client is not None:
        raise ValueError(f"{profile.name} has an Xray client already; reroll it")
    drop_peer = peer if "awg" in given and body.awg is None else None
    drop_client = client if "xray" in given and body.xray is None else None
    keep_peer = None if drop_peer else peer
    keep_client = None if drop_client else client
    if not (keep_peer or keep_client or body.awg or body.xray):
        raise ValueError("a profile needs AmneziaWG, Xray or both")

    name = body.name.strip()
    if name != profile.name:
        if session.exec(select(Profile).where(Profile.name == name)).first():
            raise DuplicateProfile(name)
    if (keep_client and name != keep_client.email) or body.xray is not None:
        _name_for_xray(session, name, keep_client)

    interface = (
        _issuable_interface(session, body.awg.interface_id)
        if body.awg is not None
        else (_interface_of(session, keep_peer) if keep_peer else None)
    )
    inbound = (
        _issuable_inbound(session, body.xray.inbound_id)
        if body.xray is not None
        else (session.get(Inbound, keep_client.inbound_id) if keep_client else None)
    )
    if interface and inbound and interface.node_id != inbound.node_id:
        raise ValueError("the interface and the inbound are on different agents")
    if body.awg is not None:
        clash = select(AwgPeer).where(AwgPeer.public_key == body.awg.public_key)
        if session.exec(clash).first() is not None:
            raise DuplicateProfile(body.awg.public_key)

    allowed = _clean(body.allowed_ips) if "allowed_ips" in given else None
    for item in (allowed or "").split(","):
        if item.strip():
            ip_network(item.strip(), strict=False)

    profile.name = name
    profile.note = _clean(body.note)
    profile.dns = _clean(body.dns)
    profile.mtu = body.mtu
    session.add(profile)
    session.flush()

    added_peer = None
    if interface is not None and body.awg is not None:
        added_peer = AwgPeer(
            profile_id=int(profile.id or 0),
            interface_id=int(interface.id or 0),
            public_key=body.awg.public_key,
            assigned_ip=pool.allocate(session, interface),
            allowed_ips=interface.client_allowed_ips,
            enabled=profile.enabled,
        )
    target = keep_peer or added_peer
    if target is not None and interface is not None and "allowed_ips" in given:
        target.allowed_ips = allowed or interface.client_allowed_ips
    if added_peer is not None and interface is not None:
        added_peer.issued_digest = _digest(interface, added_peer, profile)
        session.add(added_peer)
    added_client = None
    link = None
    if inbound is not None and body.xray is not None:
        added_client = XrayClient(
            profile_id=int(profile.id or 0),
            inbound_id=int(inbound.id or 0),
            email=name,
            flow=inbound.flow,
        )
        session.add(added_client)
        link = clientlink.render(inbound, str(body.xray.id), name)

    owner: Interface | Inbound | None = interface or inbound
    node = node_of(session, owner.node_id) if owner else None
    undo: list[Any] = []
    try:
        if node is not None:
            _push_edit(
                settings,
                node,
                interface,
                inbound,
                keep_client,
                name,
                added_peer,
                added_client,
                str(body.xray.id) if body.xray is not None else "",
                undo,
            )
            _drop_halves(session, settings, drop_peer, drop_client)
    except agent.AgentError:
        for step in reversed(undo):
            step()
        session.rollback()
        raise

    if keep_client is not None:
        keep_client.email = name
        session.add(keep_client)
    session.commit()
    session.refresh(profile)
    LOG.info("profile %s edited", profile.name)
    if added_peer is not None:
        issued = _issued(session, profile, added_peer, link)
        issued.profile = _read(session, profile)
        return issued
    return ProfileIssued(profile=_read(session, profile), link=link)


def _push_edit(
    settings: Settings,
    node: Node,
    interface: Interface | None,
    inbound: Inbound | None,
    client: XrayClient | None,
    name: str,
    peer: AwgPeer | None,
    added: XrayClient | None,
    identity: str,
    undo: list[Any],
) -> None:
    if client is not None and inbound is not None and client.email != name:
        old = client.email
        agent.rename_user(settings, node, inbound.tag, old, name)
        undo.append(lambda: agent.rename_user(settings, node, inbound.tag, name, old))
    if peer is not None and interface is not None and peer.enabled:
        agent.add_peer(
            settings,
            node,
            interface.name,
            peer.public_key,
            [peer.assigned_ip],
            interface.keepalive,
        )
        key = peer.public_key
        undo.append(lambda: agent.remove_peer(settings, node, interface.name, key))
    if added is not None and inbound is not None:
        agent.add_user(settings, node, inbound.tag, identity, name, added.flow)
        undo.append(lambda: agent.remove_user(settings, node, inbound.tag, name))


def _drop_halves(
    session: Session,
    settings: Settings,
    peer: AwgPeer | None,
    client: XrayClient | None,
) -> None:
    # Last, and not undone: an Xray UUID is not kept, so a removal cannot be.
    if peer is not None:
        interface = _interface_of(session, peer)
        node = node_of(session, interface.node_id)
        if peer.enabled:
            agent.remove_peer(settings, node, interface.name, peer.public_key)
        pool.release(session, peer)
        session.delete(peer)
    if client is not None:
        inbound = session.get(Inbound, client.inbound_id)
        if inbound is not None:
            node = node_of(session, inbound.node_id)
            agent.remove_user(settings, node, inbound.tag, client.email)
        session.delete(client)


def delete_profile(session: Session, settings: Settings, profile_id: int) -> None:
    """Remove the peer and the client from the node, then the rows and the stats."""
    profile = profile_of(session, profile_id)

    peer = _peer_of(session, profile)
    if peer is not None:
        interface = session.get(Interface, peer.interface_id)
        if interface is not None:
            node = node_of(session, interface.node_id)
            agent.remove_peer(settings, node, interface.name, peer.public_key)
        pool.release(session, peer)
        session.delete(peer)

    client = _client_of(session, profile)
    if client is not None:
        inbound = session.get(Inbound, client.inbound_id)
        if inbound is not None:
            node = node_of(session, inbound.node_id)
            agent.remove_user(settings, node, inbound.tag, client.email)
        session.delete(client)

    for table in (PeerCounter, TrafficHour, ProfileSession):
        session.exec(delete(table).where(col(table.profile_id) == profile.id))
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
    "header-protection-key": "HeaderProtectionKey",
    "content-padding-addition": "ContentPaddingAddition",
    "rekey-after-time": "RekeyAfterTime",
    "rekey-timeout": "RekeyTimeout",
    "reject-after-time": "RejectAfterTime",
    "keepalive-timeout": "KeepaliveTimeout",
    "max-handshake-attempts": "MaxHandshakeAttempts",
    "random-trailers": "RandomTrailers",
    "disable-cookies": "DisableCookies",
}
AGENT_NAMES = {name: field for field, name in OBFUSCATION_NAMES.items()}
REQUIRED_TO_ENABLE = ("address", "pool", "endpoint_host")
# A vless:// link without any of these looks right and never connects.
INBOUND_REQUIRED = ("endpoint_host", "public_key", "server_names", "short_id")
FLOWS = ("xtls-rprx-vision",)
FINGERPRINTS = (
    "chrome",
    "firefox",
    "safari",
    "ios",
    "android",
    "edge",
    "360",
    "qq",
    "random",
    "randomized",
)


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


def _address(reported: list[str]) -> str | None:
    found = [ip_interface(item) for item in reported]
    ipv4 = [item for item in found if item.version == 4]
    return str((ipv4 or found)[0]) if found else None


def _full_obfuscation(
    settings: Settings, node: Node, item: dict[str, Any], kept: dict[str, Any]
) -> dict[str, Any]:
    # Status leaves the header protection key out; this read carries it.
    try:
        return _obfuscation(agent.obfuscation(settings, node, item["name"]))
    except agent.AgentError as exc:
        if exc.status == 404:
            return _obfuscation(item.get("obfuscation") or {})
        name = item["name"]
        LOG.warning("agent %s: obfuscation of %s kept: %s", node.name, name, exc)
        return kept


def _discover(
    session: Session, settings: Settings, node: Node, reported: list[dict[str, Any]]
) -> None:
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
        kept = row.obfuscation or {}
        row.obfuscation = _full_obfuscation(settings, node, item, kept)
        # An agent before 0.3.3 reports no address; what the operator typed stays.
        address = _address(item.get("addresses") or [])
        if address is not None:
            if row.address and row.address != address:
                LOG.warning(
                    "agent %s: interface %s address %s is now %s",
                    node.name,
                    row.name,
                    row.address,
                    address,
                )
            row.address = address
            row.pool = row.pool or str(ip_interface(address).network)
        session.add(row)


def _discover_inbounds(
    session: Session, node: Node, reported: list[dict[str, Any]]
) -> None:
    rows = {
        row.tag: row
        for row in session.exec(select(Inbound).where(Inbound.node_id == node.id))
    }
    for item in reported:
        # Only vless is issued; the api inbound and the rest are not the panel's.
        if item.get("protocol") != "vless" or not item.get("tag"):
            continue
        row = rows.get(item["tag"])
        if row is None:
            row = Inbound(node_id=int(node.id or 0), tag=item["tag"])
            if item.get("security") == "reality" and item.get("network") == "tcp":
                row.flow = FLOWS[0]
            row.fingerprint = FINGERPRINTS[0]
            LOG.info(
                "agent %s: inbound %s discovered, disabled until configured",
                node.name,
                row.tag,
            )
        elif row.port != item.get("port") or (
            item.get("public_key") and row.public_key != item["public_key"]
        ):
            LOG.warning(
                "agent %s: inbound %s changed key or port; issued links are stale",
                node.name,
                row.tag,
            )
        row.protocol = item.get("protocol") or ""
        row.port = int(item.get("port") or 0)
        row.network = item.get("network") or "tcp"
        row.security = item.get("security") or "none"
        row.server_names = list(item.get("server_names") or [])
        row.short_ids = list(item.get("short_ids") or [])
        row.public_key = item.get("public_key") or row.public_key
        if row.short_id not in row.short_ids:
            row.short_id = row.short_ids[0] if row.short_ids else None
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
        inbounds = list(answer.get("inbounds") or [])
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
            inbounds=inbounds,
        )
        node.last_seen = check.checked_at
        _discover(session, settings, node, interfaces)
        _discover_inbounds(session, node, inbounds)

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
            check = _probe(session, settings, node, announce)
            if check.status != "down":
                stats.sample(session, settings, node)

    horizon = datetime.now(UTC) - timedelta(days=settings.check_retention)
    session.exec(delete(AgentCheck).where(col(AgentCheck.checked_at) < horizon))
    stats.prune(session, settings)
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
                label=row.label if row else None,
                dns=row.dns if row else None,
                mtu=row.mtu if row else None,
                client_allowed_ips=row.client_allowed_ips if row else None,
                keepalive=row.keepalive if row else None,
                obfuscation=row.obfuscation if row else {},
                addresses=list((item or {}).get("addresses") or []),
                missing=[
                    field for field in REQUIRED_TO_ENABLE if not getattr(row, field)
                ]
                if row
                else [],
            )
        )
    return found


def _inbound_missing(row: Inbound) -> list[str]:
    missing = [field for field in INBOUND_REQUIRED if not getattr(row, field)]
    return missing if row.security == "reality" else ["reality", *missing]


def _agent_inbounds(
    session: Session,
    node: Node,
    last: AgentCheck | None,
) -> list[AgentInbound]:
    reported = {item["tag"]: item for item in ((last.inbounds or []) if last else [])}
    rows = session.exec(
        select(Inbound).where(Inbound.node_id == node.id).order_by(Inbound.tag)
    ).all()
    return [
        AgentInbound(
            id=row.id,
            tag=row.tag,
            present=row.tag in reported,
            clients=int(reported.get(row.tag, {}).get("clients") or 0),
            protocol=row.protocol,
            port=row.port,
            network=row.network,
            security=row.security,
            server_names=row.server_names,
            short_ids=row.short_ids,
            public_key=row.public_key,
            enabled=row.enabled,
            endpoint_host=row.endpoint_host,
            flow=row.flow,
            fingerprint=row.fingerprint,
            short_id=row.short_id,
            label=row.label,
            missing=_inbound_missing(row),
        )
        for row in rows
    ]


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
                inbounds=_agent_inbounds(session, node, last),
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


def set_interface_obfuscation(
    session: Session,
    settings: Settings,
    interface_id: int,
    body: ObfuscationUpdate,
) -> AgentRead:
    """Change the obfuscation on the live interface; every issued profile goes stale."""
    row = session.get(Interface, interface_id)
    if row is None:
        raise UnknownInterface(str(interface_id))
    node = node_of(session, row.node_id)

    values = {}
    for name, value in body.obfuscation.items():
        field = AGENT_NAMES.get(name)
        if field is None:
            raise ValueError(f"{name} is not an obfuscation parameter")
        if isinstance(value, bool):
            value = "on" if value else "off"
        values[field] = str(value).strip()
    try:
        applied = agent.set_obfuscation(settings, node, row.name, values)
    except agent.AgentError as exc:
        if exc.status == 422:
            raise ValueError(exc.reason) from exc
        raise

    row.obfuscation = _obfuscation(applied)
    session.add(row)
    session.commit()
    LOG.warning(
        "agent %s: obfuscation of %s changed; profiles issued on it need a reroll",
        node.name,
        row.name,
    )
    return next(item for item in list_agents(session, settings) if item.id == node.id)


def update_inbound(
    session: Session,
    settings: Settings,
    inbound_id: int,
    body: InboundUpdate,
) -> AgentRead:
    """Apply what the operator set, refusing an enabled inbound that cannot issue."""
    row = session.get(Inbound, inbound_id)
    if row is None:
        raise UnknownInbound(str(inbound_id))
    node = node_of(session, row.node_id)

    for field in body.model_fields_set - {"enabled"}:
        setattr(row, field, _clean(getattr(body, field)))
    if body.enabled is not None:
        row.enabled = body.enabled

    if row.flow is not None and row.flow not in FLOWS:
        raise ValueError(f"flow {row.flow} is not one of {', '.join(FLOWS)}")
    if row.fingerprint is not None and row.fingerprint not in FINGERPRINTS:
        raise ValueError(f"fingerprint {row.fingerprint} is not a known one")
    if row.short_id is not None and row.short_id not in row.short_ids:
        raise ValueError(f"short id {row.short_id} is not configured on {row.tag}")

    missing = _inbound_missing(row)
    if row.enabled and missing:
        raise InboundNotReady(
            f"{row.tag} cannot be enabled without {', '.join(missing)}"
        )

    session.add(row)
    session.commit()
    LOG.info(
        "agent %s: inbound %s %s",
        node.name,
        row.tag,
        "enabled" if row.enabled else "disabled",
    )
    return next(item for item in list_agents(session, settings) if item.id == node.id)
