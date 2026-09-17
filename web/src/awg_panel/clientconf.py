"""Rendering the client configuration, minus the one field the panel never has.

The placeholder is replaced in the browser, where the private key was
generated. A config missing the obfuscation parameters looks correct and never
completes a handshake, so they are emitted for every profile.
"""

from __future__ import annotations

from awg_panel.models import AwgPeer, Interface

PLACEHOLDER = "__PRIVATE_KEY__"

# The order awg-quick writes them in, so a rendered file is comparable with one
# taken off a host.
OBFUSCATION_ORDER = (
    "Jc",
    "Jmin",
    "Jmax",
    "S1",
    "S2",
    "S3",
    "S4",
    "H1",
    "H2",
    "H3",
    "H4",
    "I1",
    "I2",
    "I3",
    "I4",
    "I5",
    "Itime",
)


def render(interface: Interface, peer: AwgPeer) -> str:
    """Build the .conf a client needs, with the private key left to the browser."""
    lines = [
        "[Interface]",
        f"PrivateKey = {PLACEHOLDER}",
        f"Address = {peer.assigned_ip}",
    ]
    if interface.dns:
        lines.append(f"DNS = {interface.dns}")
    if interface.mtu:
        lines.append(f"MTU = {interface.mtu}")

    for name in OBFUSCATION_ORDER:
        value = interface.obfuscation.get(name)
        if value is not None:
            lines.append(f"{name} = {value}")

    lines += [
        "",
        "[Peer]",
        f"PublicKey = {interface.server_public_key}",
        f"AllowedIPs = {peer.allowed_ips}",
        f"Endpoint = {interface.endpoint_host}:{interface.listen_port}",
    ]
    if interface.keepalive:
        lines.append(f"PersistentKeepalive = {interface.keepalive}")

    return "\n".join(lines) + "\n"
