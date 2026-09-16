"""Profiles end to end, against the stub agent."""

from __future__ import annotations

import httpx
import pytest
from conftest import StubAgent
from fastapi.testclient import TestClient

from awg_panel import agent
from awg_panel.config import Settings
from awg_panel.models import Node

KEY = "a" * 43 + "="
OTHER = "b" * 43 + "="


def _create(client: TestClient, name: str, key: str = KEY) -> dict:
    return client.post(
        "/api/v1/profiles",
        json={"name": name, "interface_id": 1, "public_key": key},
    ).json()


def test_the_interfaces_are_offered(signed_in: TestClient) -> None:
    found = signed_in.get("/api/v1/interfaces").json()
    assert [item["name"] for item in found] == ["awg-mgmt"]
    assert found[0]["obfuscation"]["Jc"] == 4


def test_creating_a_profile_pushes_the_peer(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    answer = signed_in.post(
        "/api/v1/profiles",
        json={"name": "laptop", "interface_id": 1, "public_key": KEY},
    )
    assert answer.status_code == 201

    body = answer.json()
    assert body["profile"]["peer"]["assigned_ip"] == "10.8.0.2/32"
    assert "__PRIVATE_KEY__" in body["config_template"]
    assert stub.calls == [("add", "gateway", "awg-mgmt", KEY, ("10.8.0.2/32",))]


def test_a_duplicate_name_is_409(signed_in: TestClient) -> None:
    _create(signed_in, "laptop")
    answer = signed_in.post(
        "/api/v1/profiles",
        json={"name": "laptop", "interface_id": 1, "public_key": OTHER},
    )
    assert answer.status_code == 409


def test_an_unknown_interface_is_404(signed_in: TestClient) -> None:
    answer = signed_in.post(
        "/api/v1/profiles",
        json={"name": "laptop", "interface_id": 99, "public_key": KEY},
    )
    assert answer.status_code == 404


def test_a_refusing_node_leaves_no_profile(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    stub.fail = True
    answer = signed_in.post(
        "/api/v1/profiles",
        json={"name": "laptop", "interface_id": 1, "public_key": KEY},
    )
    assert answer.status_code == 502
    assert signed_in.get("/api/v1/profiles").json() == []


def test_deleting_a_profile_removes_the_peer(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    created = _create(signed_in, "laptop")
    profile_id = created["profile"]["id"]

    assert signed_in.delete(f"/api/v1/profiles/{profile_id}").status_code == 204
    assert signed_in.get("/api/v1/profiles").json() == []
    assert ("remove", "gateway", "awg-mgmt", KEY) in stub.calls


def test_a_deleted_address_is_not_reused_at_once(signed_in: TestClient) -> None:
    created = _create(signed_in, "laptop")
    signed_in.delete(f"/api/v1/profiles/{created['profile']['id']}")

    again = _create(signed_in, "phone", OTHER)
    assert again["profile"]["peer"]["assigned_ip"] == "10.8.0.3/32"


def test_drift_reports_what_the_node_does_not_have(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    _create(signed_in, "laptop")
    stub.peers.clear()

    body = signed_in.get("/api/v1/nodes/1/drift").json()
    assert body["reachable"] is True
    assert body["missing_on_node"] == [KEY]


def test_drift_says_when_the_node_is_unreachable(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    stub.fail = True
    body = signed_in.get("/api/v1/nodes/1/drift").json()
    assert body["reachable"] is False


def test_drift_of_an_unknown_node_is_404(signed_in: TestClient) -> None:
    assert signed_in.get("/api/v1/nodes/99/drift").status_code == 404


def test_the_agents_are_probed_and_remembered(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    found = signed_in.get("/api/v1/agents").json()
    assert stub.probed == ["http://127.0.0.1:8081"]
    assert [item["name"] for item in found] == ["gateway"]
    assert found[0]["status"] == "up"
    assert found[0]["version"] == "0.1.2"
    assert found[0]["interfaces"][1]["error"].endswith("Permission denied")

    nodes = signed_in.get("/api/v1/nodes").json()
    assert nodes[0]["status"] == "up"
    assert nodes[0]["last_seen"] is not None


def test_an_unreachable_agent_is_down_with_its_reason(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    stub.fail = True
    found = signed_in.get("/api/v1/agents").json()
    assert found[0]["status"] == "down"
    assert found[0]["error"] == "gateway is unreachable: ConnectError()"
    assert signed_in.get("/api/v1/nodes").json()[0]["status"] == "down"


def test_a_call_goes_to_the_node_endpoint(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def request(method: str, url: str, **_: object) -> httpx.Response:
        seen.append(url)
        return httpx.Response(422, json={"detail": "interface 'awg9' is not managed"})

    monkeypatch.setattr(httpx, "request", request)
    node = Node(name="edge", endpoint="http://192.168.201.1:3000/")
    with pytest.raises(agent.AgentError) as error:
        agent.state(settings, node)

    assert seen == ["http://192.168.201.1:3000/v1/state"]
    assert error.value.status == 422
    assert error.value.reason == "edge answered 422: interface 'awg9' is not managed"
