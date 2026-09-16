"""The routes, end to end against the fake host."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import KEY_A, KEY_B, SOURCE, TOKEN, UUID_B, argv_log
from fastapi.testclient import TestClient

from awg_agent.app import create_app
from awg_agent.config import Settings


def test_state_carries_both_sides(client: TestClient) -> None:
    body = client.get("/v1/state").json()
    assert [item["name"] for item in body["interfaces"]] == ["awg0"]
    assert [item["tag"] for item in body["inbounds"]] == ["vless-in"]


def test_list_and_show_a_peer(client: TestClient) -> None:
    listed = client.get("/v1/awg/awg0/peers").json()
    assert [peer["public_key"] for peer in listed] == [KEY_A]

    shown = client.get(f"/v1/awg/awg0/peers/{KEY_A}")
    assert shown.status_code == 200
    assert shown.json()["allowed_ips"] == ["10.8.0.2/32"]


def test_an_absent_peer_is_404(client: TestClient) -> None:
    assert client.get(f"/v1/awg/awg0/peers/{KEY_B}").status_code == 404


def test_add_a_peer(client: TestClient, host: Path) -> None:
    answer = client.post(
        "/v1/awg/awg0/peers",
        json={"public_key": KEY_B, "allowed_ips": ["10.8.0.5"]},
    )
    assert answer.status_code == 201
    assert answer.json()["allowed_ips"] == ["10.8.0.5/32"]
    assert ["set", "awg0", "peer", KEY_B, "allowed-ips", "10.8.0.5/32"] in argv_log(
        host
    )
    assert ["showconf", "awg0"] in argv_log(host)


def test_adding_a_peer_twice_is_409(client: TestClient) -> None:
    body = {"public_key": KEY_A, "allowed_ips": ["10.8.0.2"]}
    assert client.post("/v1/awg/awg0/peers", json=body).status_code == 409


def test_a_bad_public_key_is_422(client: TestClient, host: Path) -> None:
    answer = client.post(
        "/v1/awg/awg0/peers",
        json={"public_key": "; reboot", "allowed_ips": ["10.8.0.5"]},
    )
    assert answer.status_code == 422
    assert not [line for line in argv_log(host) if line[:1] == ["set"]]


def test_an_unmanaged_interface_is_422(client: TestClient) -> None:
    assert client.get("/v1/awg/awg9/peers").status_code == 422


def test_delete_a_peer(client: TestClient) -> None:
    assert client.delete(f"/v1/awg/awg0/peers/{KEY_A}").status_code == 204
    assert client.get("/v1/awg/awg0/peers").json() == []


def test_a_failing_tool_is_502(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_AWG_FAIL", "1")
    answer = client.get("/v1/awg/awg0/peers")
    assert answer.status_code == 502
    assert "Operation not permitted" not in answer.text


def test_xray_users(client: TestClient, settings: Settings) -> None:
    listed = client.get("/v1/xray/vless-in/users").json()
    assert [user["email"] for user in listed] == ["one@node"]

    added = client.post(
        "/v1/xray/vless-in/users",
        json={"id": UUID_B, "email": "two@node", "flow": "xtls-rprx-vision"},
    )
    assert added.status_code == 201

    assert client.get("/v1/xray/vless-in/users/two@node").status_code == 200
    assert client.delete("/v1/xray/vless-in/users/two@node").status_code == 204

    written = json.loads(settings.xray_config.read_text(encoding="utf-8"))
    emails = [c["email"] for c in written["inbounds"][0]["settings"]["clients"]]
    assert emails == ["one@node"]


def test_an_unknown_inbound_is_404(client: TestClient) -> None:
    assert client.get("/v1/xray/absent/users").status_code == 404


def test_the_request_id_is_echoed(client: TestClient) -> None:
    answer = client.get("/v1/health", headers={"X-Request-Id": "abc123"})
    assert answer.headers["X-Request-Id"] == "abc123"


def test_status_reports_what_awg_shows(client: TestClient, host: Path) -> None:
    body = client.get("/v1/status").json()
    assert body["error"] is None
    assert body["interfaces"] == [
        {"name": "awg0", "present": True, "peers": 1, "error": None}
    ]
    assert not [line for line in argv_log(host) if "dump" in line]


def test_status_names_an_interface_awg_does_not_list(settings: Settings) -> None:
    wider = settings.model_copy(update={"interfaces": ["awg0", "awg9"]})
    with TestClient(create_app(wider), client=SOURCE) as test_client:
        body = test_client.get(
            "/v1/status", headers={"Authorization": f"Bearer {TOKEN}"}
        ).json()
    assert body["interfaces"][1] == {
        "name": "awg9",
        "present": False,
        "peers": 0,
        "error": "not listed by awg",
    }


def test_status_carries_the_failure_instead_of_a_502(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_AWG_FAIL", "1")
    answer = client.get("/v1/status")
    assert answer.status_code == 200
    reason = "exited 1: awg: RTNETLINK answers: Operation not permitted"
    assert answer.json()["error"] == reason
    assert answer.json()["interfaces"][0]["error"] == reason


def test_status_needs_the_token(client: TestClient) -> None:
    del client.headers["Authorization"]
    assert client.get("/v1/status").status_code == 401
