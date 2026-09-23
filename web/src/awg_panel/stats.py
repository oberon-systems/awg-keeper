"""Traffic and sessions per profile, sampled on every healthcheck round.

The agents only ever report counters since the tunnel or Xray started, so each
sample is turned into a delta against the one before it and added to the hour
it fell in. A session is a stretch in which the peer kept handshaking, or the
Xray client kept moving traffic.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from typing import Any

from sqlalchemy import delete
from sqlmodel import Session, col, select

from awg_panel import agent
from awg_panel.config import Settings
from awg_panel.models import (
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
    Bucket,
    OwnStats,
    ProfileStats,
    ProtocolStats,
    SessionRead,
)

LOG = logging.getLogger(__name__)

# A peer that keeps a session up handshakes every two minutes.
IDLE = timedelta(seconds=180)
PERIODS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}
RECENT = 5


def _utc(moment: datetime | None) -> datetime | None:
    if moment is None or moment.tzinfo is not None:
        return moment
    return moment.replace(tzinfo=UTC)


def _host(endpoint: str | None) -> str | None:
    if not endpoint or endpoint == "(none)":
        return None
    host = endpoint.rsplit(":", 1)[0]
    return host.strip("[]")


def _record(
    session: Session,
    profile_id: int,
    protocol: str,
    counters: tuple[int, int],
    seen_at: datetime | None,
    source: str | None,
    now: datetime,
) -> None:
    rx, tx = counters
    counter = session.exec(
        select(PeerCounter)
        .where(PeerCounter.profile_id == profile_id)
        .where(PeerCounter.protocol == protocol)
    ).first()
    if counter is None:
        counter = PeerCounter(profile_id=profile_id, protocol=protocol, rx=rx, tx=tx)
        drx = dtx = 0
    else:
        # A counter that went down was reset by a restart on the host.
        drx = rx - counter.rx if rx >= counter.rx else rx
        dtx = tx - counter.tx if tx >= counter.tx else tx
    if protocol == "xray":
        seen_at = now if drx or dtx or source else _utc(counter.seen_at)

    if drx or dtx:
        hour = now.replace(minute=0, second=0, microsecond=0)
        bucket = session.exec(
            select(TrafficHour)
            .where(TrafficHour.profile_id == profile_id)
            .where(TrafficHour.protocol == protocol)
            .where(TrafficHour.hour == hour)
        ).first() or TrafficHour(profile_id=profile_id, protocol=protocol, hour=hour)
        bucket.rx += drx
        bucket.tx += dtx
        session.add(bucket)

    open_one = session.exec(
        select(ProfileSession)
        .where(ProfileSession.profile_id == profile_id)
        .where(ProfileSession.protocol == protocol)
        .where(col(ProfileSession.ended_at).is_(None))
    ).first()
    active = seen_at is not None and now - seen_at <= IDLE
    if active and seen_at is not None:
        if open_one is None:
            open_one = ProfileSession(
                profile_id=profile_id,
                protocol=protocol,
                started_at=seen_at,
                last_seen_at=seen_at,
            )
        open_one.last_seen_at = seen_at
        open_one.source = source or open_one.source
        open_one.rx += drx
        open_one.tx += dtx
        session.add(open_one)
    elif open_one is not None:
        open_one.ended_at = open_one.last_seen_at
        session.add(open_one)

    counter.rx, counter.tx = rx, tx
    counter.seen_at = seen_at
    counter.source = source or counter.source
    counter.sampled_at = now
    session.add(counter)


def _sample_awg(
    session: Session, settings: Settings, node: Node, now: datetime
) -> None:
    peers = session.exec(
        select(AwgPeer, Interface)
        .where(AwgPeer.interface_id == Interface.id)
        .where(Interface.node_id == node.id)
    ).all()
    if not peers:
        return
    reported: dict[str, dict[str, Any]] = {}
    for entry in agent.state(settings, node, quiet=True).get("interfaces", []):
        for item in entry.get("peers", []):
            reported[str(item.get("public_key"))] = item
    for peer, _interface in peers:
        item = reported.get(peer.public_key)
        if item is None:
            continue
        handshake = int(item.get("latest_handshake") or 0)
        # The host counts what it received from the device as rx.
        _record(
            session,
            peer.profile_id,
            "awg",
            (int(item.get("transfer_tx") or 0), int(item.get("transfer_rx") or 0)),
            datetime.fromtimestamp(handshake, UTC) if handshake else None,
            _host(item.get("endpoint")),
            now,
        )


def _sample_xray(
    session: Session, settings: Settings, node: Node, now: datetime
) -> None:
    clients = session.exec(
        select(XrayClient)
        .join(Inbound, col(XrayClient.inbound_id) == col(Inbound.id))
        .where(Inbound.node_id == node.id)
    ).all()
    if not clients:
        return
    answer = agent.xray_stats(settings, node)
    if not answer.get("enabled"):
        return
    reported = {item.get("email"): item for item in answer.get("users", [])}
    for client in clients:
        item = reported.get(client.email)
        if item is None:
            continue
        ips = item.get("online_ips") or []
        _record(
            session,
            client.profile_id,
            "xray",
            (int(item.get("downlink") or 0), int(item.get("uplink") or 0)),
            None,
            ips[0] if ips else None,
            now,
        )


def sample(
    session: Session,
    settings: Settings,
    node: Node,
    now: datetime | None = None,
) -> None:
    """Take one sample of every profile on the node. The caller commits."""
    moment = now or datetime.now(UTC)
    for sampler in (_sample_awg, _sample_xray):
        try:
            sampler(session, settings, node, moment)
        except agent.AgentError as exc:
            LOG.debug("agent %s: no stats sample: %s", node.name, exc.reason)


def prune(session: Session, settings: Settings) -> None:
    """Forget traffic and sessions older than stats_retention days."""
    horizon = datetime.now(UTC) - timedelta(days=settings.stats_retention)
    session.exec(delete(TrafficHour).where(col(TrafficHour.hour) < horizon))
    session.exec(
        delete(ProfileSession)
        .where(col(ProfileSession.ended_at).is_not(None))
        .where(col(ProfileSession.ended_at) < horizon)
    )


def _floor(moment: datetime, hourly: bool) -> datetime:
    moment = moment.replace(minute=0, second=0, microsecond=0)
    return moment if hourly else moment.replace(hour=0)


def _key(session: Session, profile: Profile, protocol: str) -> str:
    if protocol == "awg":
        peer = session.exec(
            select(AwgPeer).where(AwgPeer.profile_id == profile.id)
        ).first()
        interface = session.get(Interface, peer.interface_id) if peer else None
        if peer is None or interface is None:
            return "-"
        return f"{interface.name} \u00b7 {peer.assigned_ip}"
    client = session.exec(
        select(XrayClient).where(XrayClient.profile_id == profile.id)
    ).first()
    inbound = session.get(Inbound, client.inbound_id) if client else None
    return inbound.tag if inbound else "-"


def profile_stats(
    session: Session,
    profile: Profile,
    period: str,
    now: datetime | None = None,
) -> ProfileStats:
    """Traffic, sessions and the last connection of one profile over a period."""
    moment = now or datetime.now(UTC)
    since = moment - PERIODS[period]
    hourly = period == "24h"

    protocols = []
    if session.exec(select(AwgPeer).where(AwgPeer.profile_id == profile.id)).first():
        protocols.append("awg")
    if session.exec(
        select(XrayClient).where(XrayClient.profile_id == profile.id)
    ).first():
        protocols.append("xray")

    step = timedelta(hours=1) if hourly else timedelta(days=1)
    hours = session.exec(
        select(TrafficHour)
        .where(TrafficHour.profile_id == profile.id)
        .where(col(TrafficHour.hour) >= _floor(since, hourly))
    ).all()
    first = _floor(since, hourly) + step
    count = int(PERIODS[period] / step)
    buckets = {first + step * i: Bucket(start=first + step * i) for i in range(count)}
    for row in hours:
        bucket = buckets.get(_floor(_utc(row.hour) or row.hour, hourly))
        if bucket is not None:
            bucket.rx += row.rx
            bucket.tx += row.tx

    rows = session.exec(
        select(ProfileSession)
        .where(ProfileSession.profile_id == profile.id)
        .where(
            (col(ProfileSession.ended_at).is_(None))
            | (col(ProfileSession.ended_at) >= since)
        )
        .order_by(col(ProfileSession.started_at).desc())
    ).all()
    connected = 0
    for row in rows:
        start = max(_utc(row.started_at) or since, since)
        end = _utc(row.ended_at) or moment
        connected += max(0, int((end - start).total_seconds()))

    counters = {
        row.protocol: row
        for row in session.exec(
            select(PeerCounter).where(PeerCounter.profile_id == profile.id)
        ).all()
    }
    seen = [
        (_utc(row.seen_at), row.source)
        for row in counters.values()
        if row.seen_at is not None
    ]
    last_seen_at, last_source = (
        max(seen, key=lambda item: item[0] or moment) if seen else (None, None)
    )

    by_protocol = []
    for protocol in protocols:
        mine = [row for row in hours if row.protocol == protocol]
        counter = counters.get(protocol)
        by_protocol.append(
            ProtocolStats(
                protocol=protocol,
                key=_key(session, profile, protocol),
                rx=sum(row.rx for row in mine),
                tx=sum(row.tx for row in mine),
                last_seen_at=_utc(counter.seen_at) if counter else None,
            )
        )

    return ProfileStats(
        period=period,
        online=any(
            row.ended_at is None and moment - (_utc(row.last_seen_at) or moment) <= IDLE
            for row in rows
        ),
        last_seen_at=last_seen_at,
        last_source=last_source,
        rx=sum(row.rx for row in hours),
        tx=sum(row.tx for row in hours),
        connected_seconds=connected,
        session_count=len(rows),
        buckets=list(buckets.values()),
        protocols=by_protocol,
        sessions=[
            SessionRead(
                started_at=_utc(row.started_at) or row.started_at,
                ended_at=_utc(row.ended_at),
                protocol=row.protocol,
                source=row.source,
                traffic=row.rx + row.tx,
            )
            for row in rows[:RECENT]
        ],
    )


def own_stats(
    session: Session,
    source: str,
    period: str,
    now: datetime | None = None,
) -> OwnStats:
    """Stats of the profile whose tunnel address the request came from."""
    try:
        address = ip_address(source)
    except ValueError:
        return OwnStats(source=source)
    found = session.exec(
        select(AwgPeer, Interface, Node)
        .where(AwgPeer.assigned_ip == f"{address}/{address.max_prefixlen}")
        .where(AwgPeer.interface_id == Interface.id)
        .where(Interface.node_id == Node.id)
    ).first()
    profile = session.get(Profile, found[0].profile_id) if found else None
    if found is None or profile is None:
        return OwnStats(source=source)
    _peer, _interface, node = found
    return OwnStats(
        source=source,
        name=profile.name,
        node=node.name,
        address=str(address),
        stats=profile_stats(session, profile, period, now),
    )
