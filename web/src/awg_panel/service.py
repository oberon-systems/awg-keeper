"""What happens when a profile is created or deleted.

The panel writes its own row first and pushes to the node second, so a node
that refuses leaves nothing behind: the transaction is rolled back and the
address goes back in the pool.
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from awg_panel import agent, clientconf, pool
from awg_panel.config import Settings
from awg_panel.models import AwgPeer, Interface, Profile
from awg_panel.schemas import PeerRead, ProfileCreate, ProfileIssued, ProfileRead

LOG = logging.getLogger(__name__)


class UnknownProfile(LookupError):
    """No profile with that id."""


class UnknownInterface(LookupError):
    """No interface with that id."""


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
            agent.remove_peer(settings, interface.name, peer.public_key)
        pool.release(session, peer)
        session.delete(peer)

    session.delete(profile)
    session.commit()
