"""Driving the awg binary: read `show dump`, write with `set`.

Peers are applied one at a time and the interface is never recreated.
`awg-quick down/up` would drop every live session, so it is not used here.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from awg_agent import validate
from awg_agent.commands import CommandError, run
from awg_agent.config import Settings
from awg_agent.models import Interface, InterfaceHealth, Peer

LOG = logging.getLogger(__name__)

NONE = "(none)"
OFF = "off"


class UnknownPeer(LookupError):
    """No peer with that public key on that interface."""


class DuplicatePeer(ValueError):
    """A peer with that public key is already configured."""


def _text(value: str) -> str | None:
    return None if value in (NONE, "", OFF) else value


def _number(value: str) -> int:
    return 0 if value in (NONE, "", OFF) else int(value)


def _peer(fields: list[str]) -> Peer:
    keepalive = _number(fields[7]) if len(fields) > 7 else 0
    return Peer(
        public_key=fields[0],
        allowed_ips=[item for item in fields[3].split(",") if item and item != NONE],
        endpoint=_text(fields[2]),
        latest_handshake=_number(fields[4]),
        transfer_rx=_number(fields[5]),
        transfer_tx=_number(fields[6]),
        persistent_keepalive=keepalive or None,
    )


def version(settings: Settings) -> str | None:
    """Return the awg version, or None when the binary is not usable."""
    try:
        return run([settings.awg_bin, "--version"], settings.command_timeout).strip()
    except CommandError as exc:
        LOG.warning("awg version unavailable: %s", exc)
        return None


def interfaces(settings: Settings) -> list[str]:
    """Return the interfaces this agent may touch, in the order awg lists them."""
    names = run([settings.awg_bin, "show", "interfaces"], settings.command_timeout)
    present = names.split()
    if not settings.interfaces:
        return present
    for name in settings.interfaces:
        if name not in present:
            LOG.warning("interface %s is configured but awg does not list it", name)
    return [name for name in settings.interfaces if name in present]


def _reason(exc: CommandError) -> str:
    lines = exc.stderr.splitlines()
    detail = f"{exc.reason}: {lines[0]}" if lines else exc.reason
    return detail[:200]


def probe(settings: Settings) -> tuple[list[InterfaceHealth], str | None]:
    """Report what awg shows for every configured interface, or why it cannot.

    Only `show interfaces` and `show <iface> peers`: neither prints a private key.
    """
    try:
        present = run(
            [settings.awg_bin, "show", "interfaces"], settings.command_timeout
        ).split()
    except CommandError as exc:
        reason = _reason(exc)
        found = [
            InterfaceHealth(name=name, present=False, error=reason)
            for name in settings.interfaces
        ]
        return found, reason

    found = []
    for name in settings.interfaces or present:
        if name not in present:
            found.append(
                InterfaceHealth(name=name, present=False, error="not listed by awg")
            )
            continue
        try:
            keys = run(
                [settings.awg_bin, "show", name, "peers"], settings.command_timeout
            ).split()
        except CommandError as exc:
            found.append(InterfaceHealth(name=name, present=True, error=_reason(exc)))
            continue
        found.append(InterfaceHealth(name=name, present=True, peers=len(keys)))
    return found, None


def show(settings: Settings, iface: str) -> Interface:
    """Read one interface and its peers out of `awg show <iface> dump`."""
    name = validate.interface(iface, settings.interfaces)
    dump = run([settings.awg_bin, "show", name, "dump"], settings.command_timeout)

    lines = [line for line in dump.splitlines() if line.strip()]
    if not lines:
        return Interface(name=name)

    # The first line is the interface itself: private key, public key, port,
    # fwmark. The private key is read past and never carried anywhere.
    head = lines[0].split("\t")
    return Interface(
        name=name,
        public_key=_text(head[1]) if len(head) > 1 else None,
        listen_port=_number(head[2]) if len(head) > 2 else 0,
        fwmark=_text(head[3]) if len(head) > 3 else None,
        peers=[_peer(line.split("\t")) for line in lines[1:]],
    )


def list_peers(settings: Settings, iface: str) -> list[Peer]:
    """Every peer configured on the interface."""
    return show(settings, iface).peers


def show_peer(settings: Settings, iface: str, public_key: str) -> Peer:
    """One peer, or UnknownPeer when the interface does not have it."""
    key = validate.public_key(public_key)
    for peer in list_peers(settings, iface):
        if peer.public_key == key:
            return peer
    raise UnknownPeer(key)


def add_peer(
    settings: Settings,
    iface: str,
    public_key: str,
    allowed: list[str],
    keepalive: int | None = None,
) -> Peer:
    """Add a peer and persist the interface. Refuses to replace an existing one."""
    name = validate.interface(iface, settings.interfaces)
    key = validate.public_key(public_key)
    networks = validate.allowed_ips(allowed)

    if any(peer.public_key == key for peer in list_peers(settings, name)):
        raise DuplicatePeer(key)

    argv = [settings.awg_bin, "set", name, "peer", key, "allowed-ips", networks]
    if keepalive is not None:
        argv += ["persistent-keepalive", str(keepalive)]
    run(argv, settings.command_timeout)

    persist(settings, name)
    return show_peer(settings, name, key)


def remove_peer(settings: Settings, iface: str, public_key: str) -> None:
    """Remove a peer and persist the interface."""
    name = validate.interface(iface, settings.interfaces)
    key = validate.public_key(public_key)

    if not any(peer.public_key == key for peer in list_peers(settings, name)):
        raise UnknownPeer(key)

    run(
        [settings.awg_bin, "set", name, "peer", key, "remove"],
        settings.command_timeout,
    )
    persist(settings, name)


def persist(settings: Settings, iface: str) -> Path | None:
    """Write `awg showconf` to disk, so the peer set survives a reboot."""
    name = validate.interface(iface, settings.interfaces)
    directory = settings.awg_conf_dir
    if not directory.is_dir():
        LOG.warning("not persisting %s: %s is not a directory", name, directory)
        return None

    config = run([settings.awg_bin, "showconf", name], settings.command_timeout)
    target = directory / f"{name}.conf"
    # Through a temporary file in the same directory: a config truncated by an
    # interrupted write is an interface that does not come back up.
    staging = directory / f".{name}.conf.tmp"
    staging.write_text(config, encoding="utf-8")
    os.chmod(staging, 0o600)
    os.replace(staging, target)
    return target
