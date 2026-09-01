"""Driving Xray: the api for the running process, config.json for the next one.

`xray api adu` and `rmu` change the running instance in memory only, so every
mutation here also rewrites config.json. Doing one without the other is how
users silently disappear on the next restart.

The subcommands are used rather than generated gRPC stubs, which keeps the
protobufs out of the package; the swap is confined to this module.

Only id-based inbounds are handled in v0 - vless, the Reality case, and vmess.
Trojan and Shadowsocks key their clients differently.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from awg_agent import validate
from awg_agent.commands import CommandError, run
from awg_agent.config import Settings
from awg_agent.models import XrayInbound, XrayUser

LOG = logging.getLogger(__name__)


class UnknownInbound(LookupError):
    """config.json has no inbound with that tag."""


class UnknownUser(LookupError):
    """That inbound has no client with that email tag."""


class DuplicateUser(ValueError):
    """A client with that email tag is already configured."""


def version(settings: Settings) -> str | None:
    """Return the Xray version, or None when the binary is not usable."""
    try:
        first = run([settings.xray_bin, "version"], settings.command_timeout)
        return first.splitlines()[0].strip() if first.strip() else None
    except CommandError as exc:
        LOG.warning("xray version unavailable: %s", exc)
        return None


def _document(settings: Settings) -> dict[str, Any]:
    try:
        text = settings.xray_config.read_text(encoding="utf-8")
    except OSError as exc:
        raise CommandError([str(settings.xray_config)], f"unreadable: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CommandError([str(settings.xray_config)], f"not JSON: {exc}") from exc


def _inbound(document: dict[str, Any], tag: str) -> dict[str, Any]:
    for entry in document.get("inbounds", []):
        if entry.get("tag") == tag:
            return entry
    raise UnknownInbound(tag)


def _clients(inbound: dict[str, Any]) -> list[dict[str, Any]]:
    return inbound.setdefault("settings", {}).setdefault("clients", [])


def _user(client: dict[str, Any]) -> XrayUser:
    return XrayUser(
        email=client.get("email", ""),
        id=client.get("id", ""),
        flow=client.get("flow") or None,
        level=int(client.get("level", 0)),
    )


def _write(settings: Settings, document: dict[str, Any]) -> None:
    target = settings.xray_config
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o600
    handle, staging = tempfile.mkstemp(dir=str(target.parent), prefix=".config-")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2)
        stream.write("\n")
    os.chmod(staging, mode)
    os.replace(staging, target)


def inbounds(settings: Settings) -> list[XrayInbound]:
    """Every inbound config.json carries, with its clients."""
    document = _document(settings)
    return [
        XrayInbound(
            tag=entry.get("tag", ""),
            users=[_user(client) for client in _clients(entry)],
        )
        for entry in document.get("inbounds", [])
        if entry.get("tag")
    ]


def list_users(settings: Settings, tag: str) -> list[XrayUser]:
    """Return the clients of one inbound, read from config.json.

    The running instance is not asked: `api inbounduser` answers in protobuf
    JSON, and config.json is rewritten on every mutation anyway.
    """
    name = validate.inbound(tag)
    document = _document(settings)
    return [_user(client) for client in _clients(_inbound(document, name))]


def show_user(settings: Settings, tag: str, address: str) -> XrayUser:
    """One client, or UnknownUser when the inbound does not have it."""
    wanted = validate.email(address)
    for user in list_users(settings, tag):
        if user.email == wanted:
            return user
    raise UnknownUser(wanted)


def add_user(
    settings: Settings,
    tag: str,
    identity: str,
    address: str,
    flow: str | None = None,
    level: int = 0,
) -> XrayUser:
    """Add a client to the running instance and to config.json."""
    name = validate.inbound(tag)
    client: dict[str, Any] = {
        "id": validate.identity(identity),
        "email": validate.email(address),
        "level": level,
    }
    if flow:
        client["flow"] = validate.flow(flow)

    document = _document(settings)
    inbound = _inbound(document, name)
    clients = _clients(inbound)
    if any(item.get("email") == client["email"] for item in clients):
        raise DuplicateUser(client["email"])

    _call_add(settings, name, inbound.get("protocol", ""), client)
    clients.append(client)
    try:
        _write(settings, document)
    except OSError as exc:
        # The instance already has the client and the file does not, which is
        # exactly the state that loses users on restart. Undo the API side.
        _call_remove(settings, name, client["email"])
        raise CommandError([str(settings.xray_config)], f"unwritable: {exc}") from exc

    return _user(client)


def remove_user(settings: Settings, tag: str, address: str) -> None:
    """Remove a client from the running instance and from config.json."""
    name = validate.inbound(tag)
    wanted = validate.email(address)

    document = _document(settings)
    inbound = _inbound(document, name)
    clients = _clients(inbound)
    kept = [item for item in clients if item.get("email") != wanted]
    if len(kept) == len(clients):
        raise UnknownUser(wanted)

    _call_remove(settings, name, wanted)
    inbound["settings"]["clients"] = kept
    try:
        _write(settings, document)
    except OSError as exc:
        raise CommandError([str(settings.xray_config)], f"unwritable: {exc}") from exc


def _call_add(
    settings: Settings,
    tag: str,
    protocol: str,
    client: dict[str, Any],
) -> None:
    # `api adu` reads whole inbound objects out of a config file, so the
    # payload is a config fragment naming the tag, the protocol and one client.
    payload = {
        "inbounds": [
            {"tag": tag, "protocol": protocol, "settings": {"clients": [client]}}
        ]
    }
    handle, staging = tempfile.mkstemp(prefix="awg-keeper-adu-", suffix=".json")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream)
        run(
            [settings.xray_bin, "api", "adu", f"--server={settings.xray_api}", staging],
            settings.command_timeout,
        )
    finally:
        Path(staging).unlink(missing_ok=True)


def _call_remove(settings: Settings, tag: str, address: str) -> None:
    run(
        [
            settings.xray_bin,
            "api",
            "rmu",
            f"--server={settings.xray_api}",
            f"-tag={tag}",
            address,
        ],
        settings.command_timeout,
    )
