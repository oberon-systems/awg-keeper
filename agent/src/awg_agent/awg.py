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

# The order of `awg show <iface> dump`, in the names `awg set` takes.
OBFUSCATION_FIELDS = validate.OBFUSCATION
# `awg show <iface>` spells the 3.1 ones out, and masks the key.
SHOWN = {name.replace("-", " "): name for name in OBFUSCATION_FIELDS}
# The [Interface] keys awg-quick reads the same values from.
CONFIG_KEYS = {
    **{name: name.upper() for name in ("s1", "s2", "s3", "s4", "h1", "h2", "h3", "h4")},
    **{name: name.upper() for name in validate.SIGNATURES},
    "jc": "Jc",
    "jmin": "Jmin",
    "jmax": "Jmax",
    **{
        name: "".join(part.title() for part in name.split("-"))
        for name in (validate.HEADER_PROTECTION, *validate.RANGES, *validate.SWITCHES)
    },
}
UNSET = frozenset({"", "0", "(null)", "(hidden)", NONE})
# What awg reports for a value nobody set: plain WireGuard's.
DEFAULTS = {
    "h1": "1",
    "h2": "2",
    "h3": "3",
    "h4": "4",
    **{name: OFF for name in validate.SWITCHES},
}


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
    # Not `awg show <iface> <field>`: amneziawg-tools 3.x segfaults on an unset i1-i5.
    try:
        shown = run([settings.awg_bin, "show", name], settings.command_timeout)
    except CommandError as exc:
        LOG.warning("obfuscation of %s unavailable: %s", name, exc)
        return {}
    found = {}
    for line in shown.splitlines():
        label, _, value = line.strip().partition(": ")
        if label == "peer":
            break
        field = SHOWN.get(label)
        if field and field != validate.HEADER_PROTECTION:
            found[field] = value.strip()
    return _set(found)


def _set(found: dict[str, str]) -> dict[str, str]:
    return {
        name: value
        for name, value in found.items()
        if value not in UNSET and DEFAULTS.get(name) != value
    }


def obfuscation(settings: Settings, iface: str) -> dict[str, str]:
    """Every obfuscation value of the interface, the header protection key included."""
    name = validate.interface(iface, settings.interfaces)
    dump = run([settings.awg_bin, "show", name, "dump"], settings.command_timeout)
    lines = dump.splitlines()
    head = lines[0].split("\t") if lines else []
    # Private key, public key and port first, fwmark last.
    return _set(dict(zip(OBFUSCATION_FIELDS, head[3:-1], strict=False)))


def set_obfuscation(
    settings: Settings, iface: str, values: dict[str, str]
) -> dict[str, str]:
    """Change obfuscation values on the live interface and persist them.

    A value can be changed but not removed: `awg set` has no way to unset one.
    """
    name = validate.interface(iface, settings.interfaces)
    current = obfuscation(settings, name)
    asked = {field: str(value).strip() for field, value in values.items()}
    if all(current.get(field) == value for field, value in asked.items()):
        return current
    merged = validate.obfuscation({**current, **asked})
    changed = {
        field: merged[field]
        for field in OBFUSCATION_FIELDS
        if field in asked and current.get(field) != merged[field]
    }
    if not changed:
        return current

    argv = [settings.awg_bin, "set", name]
    secret = changed.pop(validate.HEADER_PROTECTION, None)
    for field, value in changed.items():
        argv += [field, value]
    if secret:
        # awg reads the key from a file, as it does the private one.
        argv += [validate.HEADER_PROTECTION, "/dev/stdin"]
    run(argv, settings.command_timeout, stdin=f"{secret}\n" if secret else None)

    persist(settings, name)
    return obfuscation(settings, name)


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

    Fields are asked for by name or read off `awg show <iface>`, which prints the
    private key as `(hidden)`; `private-key`, `dump` and `showconf` are not used.
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

    # The first line is the interface itself: private key, public key, port, then
    # (awg 3.x) obfuscation, fwmark last. The private key is never carried anywhere.
    head = lines[0].split("\t")
    return Interface(
        name=name,
        public_key=_text(head[1]) if len(head) > 1 else None,
        listen_port=_number(head[2]) if len(head) > 2 else 0,
        fwmark=_text(head[-1]) if len(head) > 3 else None,
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


def _key(line: str) -> str:
    return line.partition("=")[0].strip()


def _head(kept: str, shown: str) -> str:
    """Put the obfuscation lines awg shows into the file's own head."""
    keys = set(CONFIG_KEYS.values())
    fresh = [line for line in shown.splitlines() if _key(line) in keys]
    if not fresh:
        return kept
    lines = [line for line in kept.splitlines() if _key(line) not in keys]
    return "\n".join([*lines, *fresh]) + "\n"


def _split(config: str) -> tuple[str, str]:
    lines = config.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.strip().lower() == "[peer]":
            return "".join(lines[:index]), "".join(lines[index:])
    return config, ""


def persist(settings: Settings, iface: str) -> Path | None:
    """Write the peers awg shows into the interface file, so they survive a reboot.

    The file's own [Interface] section is kept: `awg showconf` knows nothing of
    Address, DNS, MTU or PostUp, and awg-quick needs every one of them. Only
    its obfuscation lines follow the live interface.
    """
    name = validate.interface(iface, settings.interfaces)
    directory = settings.awg_conf_dir
    target = directory / f"{name}.conf"
    # Through a temporary file in the same directory: a config truncated by an
    # interrupted write is an interface that does not come back up.
    staging = directory / f".{name}.conf.tmp"
    try:
        if not directory.is_dir():
            LOG.warning("not persisting %s: %s is not a directory", name, directory)
            return None
        shown = run([settings.awg_bin, "showconf", name], settings.command_timeout)
        head, peers = _split(shown)
        if target.exists():
            kept, _ = _split(target.read_text(encoding="utf-8"))
            head = _head(kept, head)
        config = head.rstrip("\n") + "\n" + (f"\n{peers}" if peers else "")
        staging.write_text(config, encoding="utf-8")
        os.chmod(staging, 0o600)
        os.replace(staging, target)
    except (CommandError, OSError) as exc:
        LOG.error("%s is applied but not persisted to %s: %s", name, target, exc)
        return None
    return target
