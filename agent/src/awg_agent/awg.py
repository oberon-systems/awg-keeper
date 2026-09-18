"""Driving the awg binary: read `show dump`, write with `set`.

Peers are applied one at a time and the interface is never recreated.
`awg-quick down/up` would drop every live session, so it is not used here.
"""

from __future__ import annotations

import json
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

OBFUSCATION_FIELDS = (
    "jc",
    "jmin",
    "jmax",
    "s1",
    "s2",
    "s3",
    "s4",
    "h1",
    "h2",
    "h3",
    "h4",
    "i1",
    "i2",
    "i3",
    "i4",
    "i5",
)
UNSET = frozenset({"", "0", "(null)", NONE})
# What `awg show` reports for a header nobody set: plain WireGuard's message types.
DEFAULT_HEADERS = {"h1": "1", "h2": "2", "h3": "3", "h4": "4"}


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


def _field(settings: Settings, name: str, field: str) -> str:
    return run(
        [settings.awg_bin, "show", name, field], settings.command_timeout
    ).strip()


def _obfuscation(settings: Settings, name: str) -> dict[str, str]:
    found = {}
    for field in OBFUSCATION_FIELDS:
        try:
            value = _field(settings, name, field)
        except CommandError:
            # An older awg does not know s3, s4 or i1-i5; the rest still counts.
            continue
        if value in UNSET or DEFAULT_HEADERS.get(field) == value:
            continue
        found[field] = value
    return found


def _addresses(settings: Settings, name: str) -> list[str]:
    try:
        answer = run(
            [settings.ip_bin, "-j", "address", "show", "dev", name],
            settings.command_timeout,
        )
        links = json.loads(answer or "[]")
    except (CommandError, ValueError) as exc:
        LOG.warning("addresses of %s unavailable: %s", name, exc)
        return []
    return [
        f"{item['local']}/{item['prefixlen']}"
        for link in links
        for item in link.get("addr_info", [])
        if item.get("family") in ("inet", "inet6") and item.get("scope") != "link"
    ]


def probe(settings: Settings) -> tuple[list[InterfaceHealth], str | None]:
    """Report what awg shows for every configured interface, or why it cannot.

    Every field is asked for by name; `private-key`, `dump` and `showconf` are not.
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
            public_key = _text(_field(settings, name, "public-key"))
            listen_port = _number(_field(settings, name, "listen-port"))
        except CommandError as exc:
            found.append(InterfaceHealth(name=name, present=True, error=_reason(exc)))
            continue
        found.append(
            InterfaceHealth(
                name=name,
                present=True,
                peers=len(keys),
                public_key=public_key,
                listen_port=listen_port,
                obfuscation=_obfuscation(settings, name),
                addresses=_addresses(settings, name),
            )
        )
    return found, None


def _describe(item: InterfaceHealth) -> str:
    if item.error:
        state = "present" if item.present else "absent"
        return f"{item.name}: {state}, {item.error}"
    port = f"listen_port {item.listen_port}"
    return f"{item.name}: up, {port}, public_key {item.public_key}"


def log_probe(
    found: list[InterfaceHealth],
    error: str | None,
    previous: dict[str, str] | None,
) -> dict[str, str]:
    """Log the probe: everything when previous is None, afterwards only what changed.

    Returns what to pass as previous next time.
    """
    current = {item.name: _describe(item) for item in found}
    if error:
        current[""] = f"awg failed: {error}"
    peers = {item.name: item.peers for item in found if item.present and not item.error}

    for name, text in current.items():
        if previous is not None and previous.get(name) == text:
            continue
        if name in peers:
            LOG.info("%s, %d peers", text, peers[name])
        else:
            LOG.error("%s", text)

    for name, text in (previous or {}).items():
        if name not in current:
            LOG.info("cleared: %s", text)

    if previous is None and not found and not error:
        LOG.error("no interfaces: none configured and awg lists none")
    return current


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


def _split(config: str) -> tuple[str, str]:
    lines = config.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.strip().lower() == "[peer]":
            return "".join(lines[:index]), "".join(lines[index:])
    return config, ""


def persist(settings: Settings, iface: str) -> Path | None:
    """Write the peers awg shows into the interface file, so they survive a reboot.

    The file's own [Interface] section is kept: `awg showconf` knows nothing of
    Address, DNS, MTU or PostUp, and awg-quick needs every one of them.
    """
    name = validate.interface(iface, settings.interfaces)
    directory = settings.awg_conf_dir
    if not directory.is_dir():
        LOG.warning("not persisting %s: %s is not a directory", name, directory)
        return None

    target = directory / f"{name}.conf"
    # Through a temporary file in the same directory: a config truncated by an
    # interrupted write is an interface that does not come back up.
    staging = directory / f".{name}.conf.tmp"
    try:
        shown = run([settings.awg_bin, "showconf", name], settings.command_timeout)
        head, peers = _split(shown)
        if target.exists():
            head, _ = _split(target.read_text(encoding="utf-8"))
        config = head.rstrip("\n") + "\n" + (f"\n{peers}" if peers else "")
        staging.write_text(config, encoding="utf-8")
        os.chmod(staging, 0o600)
        os.replace(staging, target)
    except (CommandError, OSError) as exc:
        LOG.error("%s is applied but not persisted to %s: %s", name, target, exc)
        return None
    return target
