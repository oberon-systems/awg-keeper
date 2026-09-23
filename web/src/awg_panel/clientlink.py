"""Rendering the vless:// link, with the UUID the browser generated.

A link without pbk, sni or sid looks right and never connects, so an inbound
missing any of them is refused rather than issued with a broken link.
"""

from __future__ import annotations

from urllib.parse import quote, urlencode

from awg_panel.models import Inbound


class IncompleteInbound(ValueError):
    """An inbound that lacks something the link cannot do without."""


def render(inbound: Inbound, identity: str, name: str) -> str:
    """Build the link a VLESS client imports."""
    server_name = inbound.server_names[0] if inbound.server_names else None
    needed = {
        "endpoint host": inbound.endpoint_host,
        "public key": inbound.public_key,
        "server name": server_name,
        "short id": inbound.short_id,
    }
    missing = [field for field, value in needed.items() if not value]
    if missing:
        raise IncompleteInbound(f"{inbound.tag} has no {', '.join(missing)}")

    query = {
        "type": inbound.network,
        "security": inbound.security,
        "pbk": inbound.public_key,
        "sni": server_name,
        "sid": inbound.short_id,
        "fp": inbound.fingerprint,
        "flow": inbound.flow,
        "encryption": "none",
    }
    kept = {key: value for key, value in query.items() if value}
    params = urlencode(kept, quote_via=quote)
    host = str(inbound.endpoint_host)
    if ":" in host:
        host = f"[{host}]"
    label = quote(inbound.label or name, safe="")
    return f"vless://{identity}@{host}:{inbound.port}?{params}#{label}"
