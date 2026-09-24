"""The Amnezia key: the document AmneziaVPN builds from a .conf, named."""

from __future__ import annotations

import json

from conftest import OBFUSCATION, SERVER_KEY

from awg_panel import amneziakey, clientconf
from awg_panel.models import AwgPeer, Interface


def _interface(**changes: object) -> Interface:
    fields: dict = {
        "node_id": 1,
        "name": "awg-mgmt",
        "listen_port": 51820,
        "address": "10.8.0.1/24",
        "pool": "10.8.0.0/24",
        "server_public_key": SERVER_KEY,
        "endpoint_host": "vpn.example",
        "dns": "10.8.0.1",
        "mtu": 1280,
        "obfuscation": {**OBFUSCATION, "Itime": 60},
    }
    return Interface(**{**fields, **changes})


def _peer() -> AwgPeer:
    return AwgPeer(
        profile_id=1,
        interface_id=1,
        public_key="a" * 43 + "=",
        assigned_ip="10.8.0.2/32",
    )


def _render(**changes: object) -> tuple[dict, dict]:
    document = json.loads(amneziakey.render(_interface(**changes), _peer(), "laptop"))
    awg = document["containers"][0]["awg"]
    return document, json.loads(awg["last_config"])


def test_the_label_names_the_server() -> None:
    document, _ = _render(label="ams-1 Amsterdam")
    assert document["description"] == "ams-1 Amsterdam"


def test_without_a_label_the_profile_names_it() -> None:
    document, _ = _render()
    assert document["description"] == "laptop"


def test_the_container_is_the_one_the_app_imports() -> None:
    document, _ = _render()
    assert document["defaultContainer"] == "amnezia-awg"
    assert document["containers"][0]["container"] == "amnezia-awg"
    assert document["containers"][0]["awg"]["isThirdPartyConfig"] is True
    assert document["hostName"] == "vpn.example"


def test_the_private_key_is_left_to_the_browser() -> None:
    _, last = _render()
    assert last["client_priv_key"] == clientconf.PLACEHOLDER
    assert f"PrivateKey = {clientconf.PLACEHOLDER}" in last["config"]


def test_the_config_is_the_conf_itself() -> None:
    _, last = _render()
    assert last["config"] == clientconf.render(_interface(), _peer())
    assert last["port"] == 51820
    assert last["client_ip"] == "10.8.0.2/32"
    assert last["server_pub_key"] == SERVER_KEY
    assert last["allowed_ips"] == ["0.0.0.0/0"]
    assert last["mtu"] == "1280"
    assert last["persistent_keep_alive"] == "25"


def test_obfuscation_goes_as_strings_without_itime() -> None:
    _, last = _render()
    for name, value in OBFUSCATION.items():
        assert last[name] == str(value)
    assert "Itime" not in last
    assert "Itime = 60" in last["config"]


def test_one_dns_server_fills_both() -> None:
    document, _ = _render()
    assert (document["dns1"], document["dns2"]) == ("10.8.0.1", "10.8.0.1")


def test_two_dns_servers_go_in_order() -> None:
    document, _ = _render(dns="1.1.1.1, 9.9.9.9")
    assert (document["dns1"], document["dns2"]) == ("1.1.1.1", "9.9.9.9")


def test_no_dns_leaves_the_app_default() -> None:
    document, _ = _render(dns=None)
    assert "dns1" not in document
