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


UINT16 = ("jc", "jmin", "jmax", "s1", "s2", "s3", "s4")
HEADERS = ("h1", "h2", "h3", "h4")
SIGNATURES = ("i1", "i2", "i3", "i4", "i5")
RANGES = (
    "content-padding-addition",
    "rekey-after-time",
    "rekey-timeout",
    "reject-after-time",
    "keepalive-timeout",
    "max-handshake-attempts",
)
SWITCHES = ("random-trailers", "disable-cookies")
HEADER_PROTECTION = "header-protection-key"
OBFUSCATION = (*UINT16, *HEADERS, *SIGNATURES, HEADER_PROTECTION, *RANGES, *SWITCHES)
SPAN = re.compile(r"^(\d+)(?:-(\d+))?$")
# CPS tags as amneziawg-go parses them; <c> is not among them.
SIGNATURE = re.compile(r"^(<(b 0x[0-9a-fA-F]+|r \d+|rc \d+|rd \d+|t)>)+$")


def _span(name: str, value: str, top: int) -> tuple[int, int]:
    match = SPAN.match(value)
    if not match:
        raise ValueError(f"{name} is a number or an a-b range, not {value!r}")
    low, high = int(match[1]), int(match[2] or match[1])
    if low > high or high > top:
        raise ValueError(f"{name} {value!r} is not a range within 0-{top}")
    return low, high


def obfuscation(values: dict[str, str]) -> dict[str, str]:
    """Accept an AmneziaWG 3.1 parameter set as `awg set` takes it."""
    if unknown := sorted(set(values) - set(OBFUSCATION)):
        raise ValueError(f"not an obfuscation parameter: {', '.join(unknown)}")
    found = {name: str(value).strip() for name, value in values.items()}

    for name in UINT16:
        if name in found:
            _span(name, found[name], 65535)
            if "-" in found[name]:
                raise ValueError(f"{name} is a number, not a range")
    for name in RANGES:
        if name in found:
            _span(name, found[name], 65535)
    for name in SWITCHES:
        if name in found and found[name] not in ("on", "off"):
            raise ValueError(f"{name} is on or off")
    for name in SIGNATURES:
        if name in found and not SIGNATURE.match(found[name]):
            raise ValueError(f"{name} is a chain of <b 0x..> <r n> <rc n> <rd n> <t>")

    number = {name: int(found[name]) for name in UINT16 if name in found}
    if number.get("jmin", 0) > number.get("jmax", 65535):
        raise ValueError("jmin is above jmax")
    if "s1" in number and number["s1"] + 56 == number.get("s2"):
        raise ValueError("s1 + 56 equals s2, the plain WireGuard sizes again")

    headers = [found[name] for name in HEADERS if name in found]
    if headers:
        if len(headers) != len(HEADERS):
            raise ValueError("h1-h4 are given all four or not at all")
        spans = sorted(_span("h1-h4", item, 4294967295) for item in headers)
        if spans[0][0] < 5:
            raise ValueError("h1-h4 are above 4")
        pairs = zip(spans, spans[1:], strict=False)
        if any(left[1] >= right[0] for left, right in pairs):
            raise ValueError("h1-h4 have to be four ranges that do not overlap")

    if found.get(HEADER_PROTECTION):
        if not PUBLIC_KEY.match(found[HEADER_PROTECTION]):
            raise ValueError(f"{HEADER_PROTECTION} is 32 bytes of base64")
        if any(number.get(name, 0) < 12 for name in ("s1", "s2", "s3", "s4")):
            raise ValueError("header protection needs s1-s4 of 12 and more")
    return found
