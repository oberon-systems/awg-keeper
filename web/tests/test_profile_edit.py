"""Editing a profile: its name, its overrides, and the halves it owns."""

from __future__ import annotations

import pytest
from conftest import INBOUND, StubAgent
from fastapi.testclient import TestClient

KEY = "a" * 43 + "="
OTHER = "o" * 43 + "="
UUID = "2f9c1e7a-4b3d-4e8f-9a61-5d0c7b2e8f14"


def _create(client: TestClient, **halves: dict) -> dict:
    answer = client.post("/api/v1/profiles", json={"name": "laptop", **halves})
    assert answer.status_code == 201
    return answer.json()["profile"]


def _edit(client: TestClient, **fields: object) -> dict:
    answer = client.put("/api/v1/profiles/1", json={"name": "laptop", **fields})
    assert answer.status_code == 200, answer.text
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


def test_a_new_profile_is_not_flagged(signed_in: TestClient) -> None:
    profile = _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    assert profile["peer"]["reroll"] is False


def test_name_and_note_apply_without_a_reroll(
    signed_in: TestClient, stub: StubAgent
) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    calls = len(stub.calls)
    body = _edit(signed_in, name="phone", note="Pixel 8")
    assert body["profile"]["name"] == "phone"
    assert body["profile"]["note"] == "Pixel 8"
    assert body["profile"]["peer"]["reroll"] is False
    assert body["config_template"] is None
    assert len(stub.calls) == calls


def test_a_dns_override_asks_for_a_reroll_that_clears_it(
    signed_in: TestClient,
) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    body = _edit(signed_in, dns="1.1.1.1", mtu=1200)
    assert body["profile"]["dns"] == "1.1.1.1"
    assert body["profile"]["peer"]["reroll"] is True

    answer = signed_in.post(
        "/api/v1/profiles/1/reissue", json={"awg": {"public_key": OTHER}}
    )
    assert "DNS = 1.1.1.1" in answer.json()["config_template"]
    assert "MTU = 1200" in answer.json()["config_template"]
    assert answer.json()["profile"]["peer"]["reroll"] is False


def test_an_empty_allowed_ips_takes_the_interface_one(signed_in: TestClient) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    body = _edit(signed_in, allowed_ips="10.0.0.0/8")
    assert body["profile"]["peer"]["allowed_ips"] == "10.0.0.0/8"
    body = _edit(signed_in, allowed_ips="")
    assert body["profile"]["peer"]["allowed_ips"] == "0.0.0.0/0"


def test_an_interface_change_flags_the_profiles_on_it(signed_in: TestClient) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    signed_in.patch("/api/v1/interfaces/1", json={"dns": "9.9.9.9"})
    profile = signed_in.get("/api/v1/profiles/1").json()
    assert profile["peer"]["reroll"] is True


def test_adding_xray_renders_the_link_once(
    inbound: TestClient, stub: StubAgent
) -> None:
    _create(inbound, awg={"interface_id": 1, "public_key": KEY})
    body = _edit(inbound, xray={"inbound_id": 1, "id": UUID})
    assert body["link"].startswith("vless://")
    assert body["config_template"] is None
    assert stub.users == ["laptop"]


def test_a_rename_moves_the_xray_tag(inbound: TestClient, stub: StubAgent) -> None:
    _create(inbound, xray={"inbound_id": 1, "id": UUID})
    body = _edit(inbound, name="phone")
    assert body["profile"]["xray"]["email"] == "phone"
    assert ("rename_user", "gateway", "reality-443", "laptop", "phone") in stub.calls


def test_removing_a_half_takes_it_off_the_node(
    inbound: TestClient, stub: StubAgent
) -> None:
    _create(
        inbound,
        awg={"interface_id": 1, "public_key": KEY},
        xray={"inbound_id": 1, "id": UUID},
    )
    body = _edit(inbound, awg=None)
    assert body["profile"]["peer"] is None
    assert stub.peers == []
    assert stub.users == ["laptop"]


def test_removing_the_last_half_is_refused(signed_in: TestClient) -> None:
    _create(signed_in, awg={"interface_id": 1, "public_key": KEY})
    answer = signed_in.put("/api/v1/profiles/1", json={"name": "laptop", "awg": None})
    assert answer.status_code == 422


def test_a_refusing_node_leaves_the_profile_as_it_was(
    inbound: TestClient, stub: StubAgent
) -> None:
    _create(inbound, awg={"interface_id": 1, "public_key": KEY})
    stub.fail_xray = True
    answer = inbound.put(
        "/api/v1/profiles/1",
        json={"name": "phone", "xray": {"inbound_id": 1, "id": UUID}},
    )
    assert answer.status_code == 502
    assert inbound.get("/api/v1/profiles/1").json()["name"] == "laptop"
