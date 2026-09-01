"""The injection boundary: every value that reaches a command line.

Nothing here trusts the caller. A value either comes back in the exact shape
the tool expects or raises ValueError, which the API turns into a 422. The
leading character is constrained everywhere so no value can be read as an
option by the program it is passed to.
"""

from __future__ import annotations

import re
from ipaddress import ip_network
from uuid import UUID

# 32 bytes of key, base64 encoded: 43 characters of payload and the padding.
PUBLIC_KEY = re.compile(r"^[A-Za-z0-9+/]{43}=$")
# IFNAMSIZ is 16 including the terminator.
INTERFACE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,14}$")
INBOUND = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
EMAIL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]{0,63}$")
FLOW = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def public_key(value: str) -> str:
    """Accept a WireGuard public key, in the only shape awg prints one."""
    if not PUBLIC_KEY.match(value):
        raise ValueError("not a public key: 44 base64 characters expected")
    return value


def interface(value: str, allowed: list[str] | tuple[str, ...] = ()) -> str:
    """Accept an interface name, and only one the deployment named."""
    if not INTERFACE.match(value):
        raise ValueError(f"not an interface name: {value!r}")
    if allowed and value not in allowed:
        raise ValueError(f"interface {value!r} is not managed by this agent")
    return value


def address(value: str) -> str:
    """Accept a host or a network, normalised the way awg writes it back."""
    try:
        network = ip_network(value, strict=False)
    except ValueError as exc:
        raise ValueError(f"not an address: {value!r}: {exc}") from exc
    return str(network)


def allowed_ips(values: list[str]) -> str:
    """Accept the allowed-ips list as the single argument awg takes."""
    if not values:
        raise ValueError("allowed-ips must name at least one network")
    return ",".join(address(item) for item in values)


def identity(value: str) -> str:
    """Accept an Xray client id, which is a UUID and nothing else."""
    try:
        return str(UUID(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"not a uuid: {value!r}") from exc


def inbound(value: str) -> str:
    """Accept an Xray inbound tag."""
    if not INBOUND.match(value):
        raise ValueError(f"not an inbound tag: {value!r}")
    return value


def email(value: str) -> str:
    """Accept an Xray user tag, which the API addresses a user by."""
    if not EMAIL.match(value):
        raise ValueError(f"not a user tag: {value!r}")
    return value


def flow(value: str) -> str:
    """Accept an Xray flow name, such as xtls-rprx-vision."""
    if not FLOW.match(value):
        raise ValueError(f"not a flow: {value!r}")
    return value
