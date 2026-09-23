"""The vless:// link: every parameter, the escaping, and refusing a broken one."""

from __future__ import annotations

import pytest

from awg_panel import clientlink
from awg_panel.models import Inbound

UUID = "2f9c1e7a-4b3d-4e8f-9a61-5d0c7b2e8f14"


def _inbound(**changes: object) -> Inbound:
    fields: dict[str, object] = {
        "node_id": 1,
        "tag": "reality-443",
        "port": 443,
        "network": "tcp",
        "security": "reality",
        "server_names": ["www.example.com"],
        "short_ids": ["0123456789abcdef"],
        "public_key": "pbk_Key-1",
        "endpoint_host": "vpn.example",
        "flow": "xtls-rprx-vision",
        "fingerprint": "chrome",
        "short_id": "0123456789abcdef",
    }
    fields.update(changes)
    return Inbound(**fields)


def test_every_parameter_is_carried() -> None:
    assert clientlink.render(_inbound(), UUID, "phone") == (
        f"vless://{UUID}@vpn.example:443?type=tcp&security=reality&pbk=pbk_Key-1"
        "&sni=www.example.com&sid=0123456789abcdef&fp=chrome&flow=xtls-rprx-vision"
        "&encryption=none#phone"
    )


def test_the_label_is_escaped_and_preferred() -> None:
    link = clientlink.render(_inbound(label="ams-1 reality/2"), UUID, "phone")
    assert link.endswith("#ams-1%20reality%2F2")


def test_an_ipv6_host_is_bracketed() -> None:
    link = clientlink.render(_inbound(endpoint_host="2001:db8::1"), UUID, "phone")
    assert "@[2001:db8::1]:443?" in link


def test_no_flow_leaves_the_parameter_out() -> None:
    assert "flow=" not in clientlink.render(_inbound(flow=None), UUID, "phone")


@pytest.mark.parametrize(
    ("changes", "missing"),
    [
        ({"public_key": None}, "public key"),
        ({"server_names": []}, "server name"),
        ({"short_id": None}, "short id"),
        ({"endpoint_host": None}, "endpoint host"),
    ],
)
def test_an_incomplete_inbound_is_refused(changes: dict, missing: str) -> None:
    with pytest.raises(clientlink.IncompleteInbound, match=missing):
        clientlink.render(_inbound(**changes), UUID, "phone")
