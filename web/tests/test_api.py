"""Profiles end to end, against the stub agent."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from conftest import SOURCE, StubAgent
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from awg_panel import agent
from awg_panel.app import create_app
from awg_panel.config import Settings
from awg_panel.db import build_engine
from awg_panel.models import AgentCheck, Interface, Node

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


def test_listing_the_agents_probes_nothing(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    found = signed_in.get("/api/v1/agents").json()
    assert stub.probed == []
    assert [item["name"] for item in found] == ["gateway"]
    assert found[0]["status"] == "unknown"
    assert found[0]["checked_at"] is None
    assert [item["name"] for item in found[0]["interfaces"]] == ["awg-mgmt"]


def test_a_probe_is_recorded_and_remembered(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    found = signed_in.post("/api/v1/agents/probe").json()
    assert stub.probed == ["http://127.0.0.1:8081"]
    assert found[0]["status"] == "degraded"
    assert found[0]["version"] == "0.1.2"
    assert found[0]["checked_at"].endswith("Z") or "+00:00" in found[0]["checked_at"]
    assert found[0]["interfaces"][1]["error"].endswith("Permission denied")

    again = signed_in.get("/api/v1/agents").json()
    assert again == found
    nodes = signed_in.get("/api/v1/nodes").json()
    assert nodes[0]["status"] == "degraded"
    assert nodes[0]["last_seen"] is not None

    checks = signed_in.get("/api/v1/agents/1/checks").json()
    assert [check["status"] for check in checks] == ["degraded"]
    assert checks[0]["interfaces"][0]["name"] == "awg-mgmt"


def test_an_unreachable_agent_is_down_with_its_reason(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    stub.fail = True
    found = signed_in.post("/api/v1/agents/probe").json()
    assert found[0]["status"] == "down"
    assert found[0]["error"] == "gateway is unreachable: ConnectError()"
    assert signed_in.get("/api/v1/nodes").json()[0]["status"] == "down"
    assert signed_in.get("/api/v1/agents/1/checks").json()[0]["status"] == "down"


def test_the_checks_of_an_unknown_agent_are_404(signed_in: TestClient) -> None:
    assert signed_in.get("/api/v1/agents/99/checks").status_code == 404


def test_old_checks_are_pruned(
    signed_in: TestClient,
    settings: Settings,
) -> None:
    with Session(build_engine(settings)) as session:
        session.add(
            AgentCheck(
                node_id=1,
                status="up",
                checked_at=datetime.now(UTC)
                - timedelta(days=settings.check_retention + 1),
            )
        )
        session.commit()
    signed_in.post("/api/v1/agents/probe")
    assert len(signed_in.get("/api/v1/agents/1/checks").json()) == 1


def test_a_reported_interface_is_discovered_disabled(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    stub.extra.append(
        {
            "name": "awg-new",
            "present": True,
            "peers": 0,
            "public_key": KEY,
            "listen_port": 51821,
        }
    )
    found = signed_in.post("/api/v1/agents/probe").json()
    new = next(item for item in found[0]["interfaces"] if item["name"] == "awg-new")
    assert new["enabled"] is False
    assert new["id"] is not None
    assert new["missing"] == ["address", "pool", "endpoint_host"]
    assert [item["name"] for item in signed_in.get("/api/v1/interfaces").json()] == [
        "awg-mgmt"
    ]

    refused = signed_in.patch(f"/api/v1/interfaces/{new['id']}", json={"enabled": True})
    assert refused.status_code == 422
    assert "address, pool, endpoint_host" in refused.json()["detail"]

    outside = signed_in.patch(
        f"/api/v1/interfaces/{new['id']}",
        json={"address": "10.9.0.1/24", "pool": "10.10.0.0/24"},
    )
    assert outside.status_code == 422

    enabled = signed_in.patch(
        f"/api/v1/interfaces/{new['id']}",
        json={
            "enabled": True,
            "address": "10.9.0.1/24",
            "pool": "10.9.0.0/24",
            "endpoint_host": "vpn.example",
        },
    )
    assert enabled.status_code == 200
    now = next(
        item for item in enabled.json()["interfaces"] if item["name"] == "awg-new"
    )
    assert now["missing"] == []
    offered = signed_in.get("/api/v1/interfaces").json()
    assert [item["name"] for item in offered] == ["awg-mgmt", "awg-new"]


def test_a_reported_address_sets_address_and_pool(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    stub.extra.append(
        {
            "name": "awg-guests",
            "present": True,
            "peers": 0,
            "public_key": KEY,
            "listen_port": 51822,
            "addresses": ["fd00::1/64", "10.20.0.1/24"],
        }
    )
    found = signed_in.post("/api/v1/agents/probe").json()
    new = next(item for item in found[0]["interfaces"] if item["name"] == "awg-guests")
    assert new["address"] == "10.20.0.1/24"
    assert new["pool"] == "10.20.0.0/24"
    assert new["missing"] == ["endpoint_host"]

    enabled = signed_in.patch(
        f"/api/v1/interfaces/{new['id']}",
        json={"enabled": True, "endpoint_host": "vpn.example"},
    )
    assert enabled.status_code == 200


def test_discovery_keeps_what_the_operator_set(
    signed_in: TestClient,
    settings: Settings,
) -> None:
    signed_in.post("/api/v1/agents/probe")
    with Session(build_engine(settings)) as session:
        row = session.get(Interface, 1)
        assert row is not None
        assert row.address == "10.8.0.1/24"
        assert row.enabled is True
        assert row.obfuscation == {"Jc": 4, "Jmin": 50, "H1": 1077035230}


def test_a_disabled_interface_issues_nothing(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    assert (
        signed_in.patch("/api/v1/interfaces/1", json={"enabled": False}).status_code
        == 200
    )
    answer = signed_in.post(
        "/api/v1/profiles",
        json={"name": "laptop", "interface_id": 1, "public_key": KEY},
    )
    assert answer.status_code == 422
    assert stub.calls == []


def test_an_agent_from_the_environment_needs_no_sql(
    settings: Settings,
    stub: StubAgent,
) -> None:
    engine = build_engine(settings)
    SQLModel.metadata.create_all(engine)
    create_app(settings)
    with Session(engine) as session:
        assert [(row.name, row.endpoint) for row in session.exec(select(Node))] == [
            ("gateway", "http://127.0.0.1:8081")
        ]


def test_the_background_healthcheck_runs_without_a_request(
    settings: Settings,
    node: None,
    stub: StubAgent,
) -> None:
    looping = settings.model_copy(update={"probe_interval": 1})
    with TestClient(create_app(looping), base_url="https://testserver", client=SOURCE):
        deadline = time.monotonic() + 5
        while not stub.probed and time.monotonic() < deadline:
            time.sleep(0.05)
    assert stub.probed[:1] == ["http://127.0.0.1:8081"]


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
