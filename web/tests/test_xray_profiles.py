"""Profiles with an Xray client, and the vless:// link issued for them."""

from __future__ import annotations

import pytest
from conftest import INBOUND, REALITY_KEY, StubAgent
from fastapi.testclient import TestClient

from awg_panel.config import Settings

KEY = "a" * 43 + "="
UUID = "2f9c1e7a-4b3d-4e8f-9a61-5d0c7b2e8f14"


@pytest.fixture
def inbound(signed_in: TestClient, stub: StubAgent) -> TestClient:
    """Discover reality-443 and enable it, the way an operator would."""
    stub.inbounds = [dict(INBOUND)]
    signed_in.post("/api/v1/agents/probe")
    answer = signed_in.patch(
        "/api/v1/inbounds/1", json={"enabled": True, "endpoint_host": "vpn.example"}
    )
    assert answer.status_code == 200
    return signed_in


def test_the_enabled_inbounds_are_offered(inbound: TestClient) -> None:
    found = inbound.get("/api/v1/inbounds").json()
    assert [(item["tag"], item["port"]) for item in found] == [("reality-443", 443)]


def test_an_xray_profile_is_issued_as_a_link(
    inbound: TestClient,
    stub: StubAgent,
) -> None:
    answer = inbound.post(
        "/api/v1/profiles",
        json={"name": "phone", "xray": {"inbound_id": 1, "id": UUID}},
    )
    assert answer.status_code == 201
    body = answer.json()
    assert body["config_template"] is None
    assert body["link"] == (
        f"vless://{UUID}@vpn.example:443?type=tcp&security=reality&pbk={REALITY_KEY}"
        "&sni=www.example.com&sid=0123456789abcdef&fp=chrome&flow=xtls-rprx-vision"
        "&encryption=none#phone"
    )
    assert body["profile"]["node"] == "gateway"
    assert body["profile"]["xray"]["inbound"] == "reality-443"
    assert body["profile"]["peer"] is None
    assert stub.calls == [
        ("add_user", "gateway", "reality-443", UUID, "phone", "xtls-rprx-vision")
    ]


def test_the_uuid_is_kept_nowhere(inbound: TestClient, settings: Settings) -> None:
    inbound.post(
        "/api/v1/profiles",
        json={"name": "phone", "xray": {"inbound_id": 1, "id": UUID}},
    )
    assert UUID not in inbound.get("/api/v1/profiles").text
    assert UUID not in inbound.get("/api/v1/profiles/1").text
    files = settings.database_path.parent.glob("panel.sqlite*")
    stored = b"".join(path.read_bytes() for path in files)
    assert UUID.encode() not in stored


def test_both_protocols_on_one_profile(inbound: TestClient, stub: StubAgent) -> None:
    answer = inbound.post(
        "/api/v1/profiles",
        json={
            "name": "laptop",
            "awg": {"interface_id": 1, "public_key": KEY},
            "xray": {"inbound_id": 1, "id": UUID},
        },
    )
    assert answer.status_code == 201
    body = answer.json()
    assert "__PRIVATE_KEY__" in body["config_template"]
    assert body["link"].startswith(f"vless://{UUID}@")
    assert body["profile"]["peer"]["interface"] == "awg-mgmt"
    assert [call[0] for call in stub.calls] == ["add", "add_user"]


def test_a_refused_client_takes_the_peer_back(
    inbound: TestClient,
    stub: StubAgent,
) -> None:
    stub.fail_xray = True
    answer = inbound.post(
        "/api/v1/profiles",
        json={
            "name": "laptop",
            "awg": {"interface_id": 1, "public_key": KEY},
            "xray": {"inbound_id": 1, "id": UUID},
        },
    )
    assert answer.status_code == 502
    assert stub.peers == []
    assert inbound.get("/api/v1/profiles").json() == []


def test_deleting_removes_the_client_too(inbound: TestClient, stub: StubAgent) -> None:
    created = inbound.post(
        "/api/v1/profiles",
        json={
            "name": "laptop",
            "awg": {"interface_id": 1, "public_key": KEY},
            "xray": {"inbound_id": 1, "id": UUID},
        },
    ).json()
    profile = created["profile"]["id"]
    assert inbound.delete(f"/api/v1/profiles/{profile}").status_code == 204
    assert stub.users == []
    assert stub.calls[-1] == ("remove_user", "gateway", "reality-443", "laptop")


@pytest.mark.parametrize(
    "body",
    [
        {"name": "nothing"},
        {"name": "has space", "xray": {"inbound_id": 1, "id": UUID}},
        {"name": "phone", "xray": {"inbound_id": 1, "id": "not-a-uuid"}},
    ],
)
def test_what_cannot_be_issued_is_422(inbound: TestClient, body: dict) -> None:
    assert inbound.post("/api/v1/profiles", json=body).status_code == 422


def test_a_disabled_inbound_issues_nothing(
    inbound: TestClient,
    stub: StubAgent,
) -> None:
    inbound.patch("/api/v1/inbounds/1", json={"enabled": False})
    answer = inbound.post(
        "/api/v1/profiles",
        json={"name": "phone", "xray": {"inbound_id": 1, "id": UUID}},
    )
    assert answer.status_code == 422
    assert stub.calls == []
