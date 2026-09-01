"""The client configuration: every field but the one the panel never has."""

from __future__ import annotations

from conftest import OBFUSCATION

from awg_panel import clientconf
from awg_panel.models import AwgPeer, Interface


def _interface() -> Interface:
    return Interface(
        node_id=1,
        name="awg-mgmt",
        listen_port=51820,
        address="10.8.0.1/24",
        pool="10.8.0.0/24",
        server_public_key="c" * 43 + "=",
        endpoint_host="vpn.example",
        dns="10.8.0.1",
        mtu=1280,
        obfuscation=OBFUSCATION,
    )


def _peer() -> AwgPeer:
    return AwgPeer(
        profile_id=1,
        interface_id=1,
        public_key="a" * 43 + "=",
        assigned_ip="10.8.0.2/32",
    )


def test_the_private_key_is_a_placeholder() -> None:
    rendered = clientconf.render(_interface(), _peer())
    assert f"PrivateKey = {clientconf.PLACEHOLDER}" in rendered


def test_every_obfuscation_parameter_is_emitted() -> None:
    rendered = clientconf.render(_interface(), _peer())
    for name, value in OBFUSCATION.items():
        assert f"{name} = {value}" in rendered


def test_the_peer_section_points_at_the_gateway() -> None:
    rendered = clientconf.render(_interface(), _peer())
    assert "Endpoint = vpn.example:51820" in rendered
    assert "PublicKey = " + "c" * 43 + "=" in rendered
    assert "PersistentKeepalive = 25" in rendered


def test_an_interface_without_obfuscation_still_renders() -> None:
    bare = _interface()
    bare.obfuscation = {}
    rendered = clientconf.render(bare, _peer())
    assert "Jc = " not in rendered
    assert rendered.endswith("\n")
