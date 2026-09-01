"""Handing out addresses from an interface pool."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from ipaddress import ip_address, ip_network

from sqlmodel import Session, select

from awg_panel.models import AwgPeer, Interface, ReleasedIp

# How long a released address is left alone. A config that is still in someone's
# pocket must not start pointing at a different profile the same afternoon.
QUARANTINE = timedelta(days=7)


class PoolExhausted(RuntimeError):
    """Every address in the interface pool is taken or quarantined."""


def _taken(session: Session, interface: Interface) -> set[str]:
    rows = session.exec(
        select(AwgPeer.assigned_ip).where(AwgPeer.interface_id == interface.id)
    ).all()
    return set(rows)


def _quarantined(session: Session, interface: Interface) -> set[str]:
    since = datetime.now(UTC) - QUARANTINE
    rows = session.exec(
        select(ReleasedIp.address).where(
            ReleasedIp.interface_id == interface.id,
            ReleasedIp.released_at >= since,
        )
    ).all()
    return set(rows)


def allocate(session: Session, interface: Interface) -> str:
    """Return the lowest free address of the pool, as a /32."""
    network = ip_network(interface.pool, strict=False)
    server = ip_address(interface.address.split("/")[0])
    unavailable = _taken(session, interface) | _quarantined(session, interface)

    for candidate in network.hosts():
        if candidate == server:
            continue
        offered = f"{candidate}/{candidate.max_prefixlen}"
        if offered not in unavailable:
            return offered

    raise PoolExhausted(interface.pool)


def release(session: Session, peer: AwgPeer) -> None:
    """Record the address of a peer that is going away."""
    session.add(ReleasedIp(interface_id=peer.interface_id, address=peer.assigned_ip))
