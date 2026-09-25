"""Rendering the Amnezia key, the one client format that carries a server name.

A plain .conf imported into AmneziaVPN is named "Server 1", "Server 2" and so
on. The key is the document the app builds itself when it imports a .conf
(ImportController::extractWireGuardConfig), with the description filled in.
The browser swaps in the private key, compresses it and encodes it as vpn://.
"""

from __future__ import annotations

import json
from typing import Any

from awg_panel import clientconf
from awg_panel.models import AwgPeer, Interface, Profile

CONTAINER = "amnezia-awg"
# The app's own default for an AmneziaWG config that names no MTU.
DEFAULT_MTU = 1376


def render(
    interface: Interface, peer: AwgPeer, name: str, profile: Profile | None = None
) -> str:
    """Build the key document, with the private key left to the browser."""
    last_config: dict[str, Any] = {
        "config": clientconf.render(interface, peer, profile),
        "hostName": interface.endpoint_host,
        "port": interface.listen_port,
        "client_priv_key": clientconf.PLACEHOLDER,
        "client_ip": peer.assigned_ip,
        "server_pub_key": interface.server_public_key,
        "allowed_ips": [item.strip() for item in peer.allowed_ips.split(",")],
        "mtu": str(clientconf.mtu(interface, profile) or DEFAULT_MTU),
    }
    if interface.keepalive:
        last_config["persistent_keep_alive"] = str(interface.keepalive)
    # Itime is not among the keys the app reads back; the .conf above keeps it.
    for key in clientconf.OBFUSCATION_ORDER:
        value = interface.obfuscation.get(key)
        if value is not None and key != "Itime":
            last_config[key] = str(value)

    document: dict[str, Any] = {
        "containers": [
            {
                "container": CONTAINER,
                "awg": {
                    "last_config": json.dumps(last_config),
                    "isThirdPartyConfig": True,
                    "port": str(interface.listen_port),
                    "transport_proto": "udp",
                },
            }
        ],
        "defaultContainer": CONTAINER,
        "description": interface.label or name,
        "hostName": interface.endpoint_host,
    }
    resolvers = clientconf.dns(interface, profile) or ""
    servers = [item.strip() for item in resolvers.split(",") if item.strip()]
    if servers:
        document["dns1"] = servers[0]
        document["dns2"] = servers[1] if len(servers) > 1 else servers[0]
    return json.dumps(document)
