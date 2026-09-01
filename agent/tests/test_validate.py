"""The injection boundary. Every one of these values reaches a command line."""

from __future__ import annotations

import pytest

from awg_agent import validate

KEY = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa0="


def test_public_key_is_accepted() -> None:
    assert validate.public_key(KEY) == KEY


@pytest.mark.parametrize(
    "value",
    ["", "short=", KEY[:-1], KEY.replace("=", "!"), f"{KEY} --remove", "-" + KEY[1:]],
)
def test_a_bad_public_key_is_refused(value: str) -> None:
    with pytest.raises(ValueError):
        validate.public_key(value)


def test_interface_must_be_managed() -> None:
    assert validate.interface("awg0", ["awg0"]) == "awg0"
    with pytest.raises(ValueError):
        validate.interface("awg1", ["awg0"])


@pytest.mark.parametrize("value", ["", "-awg0", "awg 0", "a" * 16, "awg0;reboot"])
def test_a_bad_interface_is_refused(value: str) -> None:
    with pytest.raises(ValueError):
        validate.interface(value)


def test_addresses_are_normalised() -> None:
    assert validate.address("10.8.0.5") == "10.8.0.5/32"
    assert validate.address("10.8.0.5/24") == "10.8.0.0/24"
    assert (
        validate.allowed_ips(["10.8.0.5", "10.9.0.0/24"]) == "10.8.0.5/32,10.9.0.0/24"
    )


def test_empty_allowed_ips_is_refused() -> None:
    with pytest.raises(ValueError):
        validate.allowed_ips([])


def test_identity_must_be_a_uuid() -> None:
    value = "6f1f0b8e-0b1a-4c2e-9d3f-5a6b7c8d9e01"
    assert validate.identity(value) == value
    with pytest.raises(ValueError):
        validate.identity("not-a-uuid")


def test_tags_are_constrained() -> None:
    assert validate.inbound("vless-in") == "vless-in"
    assert validate.email("one@node") == "one@node"
    assert validate.flow("xtls-rprx-vision") == "xtls-rprx-vision"
    for bad in ("-tag", "tag with space", ""):
        with pytest.raises(ValueError):
            validate.inbound(bad)
