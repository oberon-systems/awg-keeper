"""Two gates in front of the API: the shared token, and the source address.

Both are pre-set by the deployment; neither can be negotiated by the caller.
"""

from __future__ import annotations

import logging
import secrets
from ipaddress import ip_address

from fastapi import Header, HTTPException, Request

from awg_agent.config import Settings

LOG = logging.getLogger(__name__)

UNAUTHENTICATED = {"WWW-Authenticate": "Bearer"}


def settings_of(request: Request) -> Settings:
    """Return the one Settings instance, put on the app by create_app()."""
    return request.app.state.settings


def require_token(request: Request, authorization: str = Header(default="")) -> None:
    """Refuse anything that does not carry the pre-set token.

    Both sides are encoded first: compare_digest raises TypeError on a string
    holding non-ASCII, which would turn a bad header into a 500.
    """
    source = request.client.host if request.client else "-"
    scheme, _, offered = authorization.partition(" ")
    if scheme.lower() != "bearer" or not offered:
        LOG.warning("refused %s: missing bearer token", source)
        raise HTTPException(401, "missing bearer token", UNAUTHENTICATED)

    expected = settings_of(request).token
    if not secrets.compare_digest(offered.encode("utf-8"), expected.encode("utf-8")):
        LOG.warning("refused %s: bad token", source)
        raise HTTPException(401, "bad token", UNAUTHENTICATED)


def require_source(request: Request) -> None:
    """Refuse anything that did not come from a pre-set subnet.

    X-Forwarded-For is deliberately not read: the agent binds an internal
    address with no proxy in front of it, so honouring the header would hand
    the allowlist to the caller.
    """
    client = request.client
    if client is None:
        raise HTTPException(403, "source address unknown")

    try:
        source = ip_address(client.host)
    except ValueError as exc:
        raise HTTPException(403, "source address unknown") from exc

    networks = settings_of(request).reachable_from()
    if not any(source in network for network in networks):
        LOG.warning("refused %s: outside the allowed subnets", source)
        raise HTTPException(403, "source address not allowed")
