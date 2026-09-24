"""Turning a profile off and on, and reissuing its keys."""

from __future__ import annotations

import json

import pytest
from conftest import INBOUND, StubAgent
from fastapi.testclient import TestClient

KEY = "a" * 43 + "="
NEW = "n" * 43 + "="
UUID = "2f9c1e7a-4b3d-4e8f-9a61-5d0c7b2e8f14"
NEW_UUID = "7d1e0c9b-2a4f-4b6e-8c3d-1f0e9a8b7c6d"


def _create(client: TestClient, **halves: dict) -> dict:
    answer = client.post("/api/v1/profiles", json={"name": "laptop", **halves})
    assert answer.status_code == 201
    return answer.json()


@pytest.fixture
def inbound(signed_in: TestClient, stub: StubAgent) -> TestClient:
    """Discover reality-443 and enable it."""
    stub.inbounds = [dict(INBOUND)]
    signed_in.post("/api/v1/agents/probe")
    signed_in.patch(
        "/api/v1/inbounds/1", json={"enabled": True, "endpoint_host": "vpn.example"}
    )
    return signed_in


def test_an_issued_profile_carries_the_amnezia_key(signed_in: TestClient) -> None:
    body = _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    document = json.loads(body["amnezia_template"])
    assert document["description"] == "laptop"
    assert "__PRIVATE_KEY__" in body["amnezia_template"]


def test_the_interface_label_names_the_key(signed_in: TestClient) -> None:
    answer = signed_in.patch("/api/v1/interfaces/1", json={"label": " ams-1 "})
    assert answer.status_code == 200
    assert answer.json()["interfaces"][0]["label"] == "ams-1"

    body = _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    assert json.loads(body["amnezia_template"])["description"] == "ams-1"


def test_turning_off_takes_the_peer_off_the_node(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})

    answer = signed_in.patch("/api/v1/profiles/1", json={"enabled": False})
    assert answer.status_code == 200
    assert answer.json()["enabled"] is False
    assert answer.json()["peer"]["enabled"] is False
    assert answer.json()["peer"]["assigned_ip"] == "10.8.0.2/32"
    assert stub.peers == []


def test_turning_on_puts_the_same_peer_back(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    signed_in.patch("/api/v1/profiles/1", json={"enabled": False})

    answer = signed_in.patch("/api/v1/profiles/1", json={"enabled": True})
    assert answer.json()["enabled"] is True
    assert stub.calls[-1] == ("add", "gateway", "awg-mgmt", KEY, ("10.8.0.2/32",))


def test_a_profile_without_a_peer_has_no_switch(inbound: TestClient) -> None:
    _create(inbound, xray={"inbound_id": 1, "id": UUID})
    answer = inbound.patch("/api/v1/profiles/1", json={"enabled": False})
    assert answer.status_code == 422


def test_a_refusing_node_leaves_the_profile_on(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    stub.fail = True
    assert signed_in.patch("/api/v1/profiles/1", json={"enabled": False}).is_error
    assert signed_in.get("/api/v1/profiles/1").json()["enabled"] is True


def test_drift_ignores_a_peer_turned_off(signed_in: TestClient) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    signed_in.patch("/api/v1/profiles/1", json={"enabled": False})
    assert signed_in.get("/api/v1/nodes/1/drift").json()["missing_on_node"] == []


def test_reissuing_swaps_the_key_on_the_same_address(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})

    answer = signed_in.post(
        "/api/v1/profiles/1/reissue", json={"awg": {"public_key": NEW}}
    )
    assert answer.status_code == 200
    body = answer.json()
    assert body["profile"]["peer"]["public_key"] == NEW
    assert body["profile"]["peer"]["assigned_ip"] == "10.8.0.2/32"
    assert "__PRIVATE_KEY__" in body["config_template"]
    assert "__PRIVATE_KEY__" in body["amnezia_template"]
    assert stub.peers == [NEW]
    assert stub.calls[-2:] == [
        ("remove", "gateway", "awg-mgmt", KEY),
        ("add", "gateway", "awg-mgmt", NEW, ("10.8.0.2/32",)),
    ]


def test_reissuing_a_peer_turned_off_touches_no_node(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    signed_in.patch("/api/v1/profiles/1", json={"enabled": False})
    calls = len(stub.calls)

    answer = signed_in.post(
        "/api/v1/profiles/1/reissue", json={"awg": {"public_key": NEW}}
    )
    assert answer.json()["profile"]["peer"]["public_key"] == NEW
    assert len(stub.calls) == calls


def test_reissuing_both_halves_renews_the_link(
    inbound: TestClient,
    stub: StubAgent,
) -> None:
    _create(
        inbound,
        awg={"interface_id": 1, "public_key": KEY},
        xray={"inbound_id": 1, "id": UUID},
    )

    answer = inbound.post(
        "/api/v1/profiles/1/reissue",
        json={"awg": {"public_key": NEW}, "xray": {"id": NEW_UUID}},
    )
    assert answer.status_code == 200
    assert answer.json()["link"].startswith(f"vless://{NEW_UUID}@")
    assert stub.calls[-2:] == [
        ("remove_user", "gateway", "reality-443", "laptop"),
        ("add_user", "gateway", "reality-443", NEW_UUID, "laptop", "xtls-rprx-vision"),
    ]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"xray": {"id": NEW_UUID}},
        {"awg": {"public_key": NEW}, "xray": {"id": NEW_UUID}},
    ],
)
def test_reissuing_needs_exactly_the_halves_owned(
    signed_in: TestClient,
    body: dict,
) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    answer = signed_in.post("/api/v1/profiles/1/reissue", json=body)
    assert answer.status_code == 422


def test_reissuing_to_a_taken_key_is_409(signed_in: TestClient) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    answer = signed_in.post(
        "/api/v1/profiles/1/reissue", json={"awg": {"public_key": KEY}}
    )
    assert answer.status_code == 409
