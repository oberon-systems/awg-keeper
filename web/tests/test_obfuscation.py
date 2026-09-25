"""The obfuscation of an interface: read in full from the agent, edited through it."""

from __future__ import annotations

from conftest import StubAgent
from fastapi.testclient import TestClient

KEY = "a" * 43 + "="
HEADER_KEY = "h" * 43 + "="


def test_the_full_read_carries_the_header_protection_key(
    signed_in: TestClient, stub: StubAgent
) -> None:
    stub.obfuscations["awg-mgmt"] = {"jc": "5", "header-protection-key": HEADER_KEY}
    agents = signed_in.post("/api/v1/agents/probe").json()
    found = agents[0]["interfaces"][0]["obfuscation"]
    assert found == {"Jc": 5, "HeaderProtectionKey": HEADER_KEY}


def test_an_old_agent_falls_back_to_the_status(signed_in: TestClient) -> None:
    agents = signed_in.post("/api/v1/agents/probe").json()
    found = agents[0]["interfaces"][0]["obfuscation"]
    assert found == {"Jc": 4, "Jmin": 50, "H1": 1077035230}


def test_an_edit_goes_through_the_agent_and_flags_the_profiles(
    signed_in: TestClient, stub: StubAgent
) -> None:
    signed_in.post(
        "/api/v1/profiles",
        json={"name": "laptop", "awg": {"interface_id": 1, "public_key": KEY}},
    )
    answer = signed_in.patch(
        "/api/v1/interfaces/1/obfuscation",
        json={"obfuscation": {"Jc": 6, "RandomTrailers": True, "H1": "100-200"}},
    )
    assert answer.status_code == 200, answer.text
    assert stub.calls[-1] == (
        "set_obfuscation",
        "gateway",
        "awg-mgmt",
        {"jc": "6", "random-trailers": "on", "h1": "100-200"},
    )
    found = answer.json()["interfaces"][0]["obfuscation"]
    assert found["RandomTrailers"] == "on"
    assert signed_in.get("/api/v1/profiles/1").json()["peer"]["reroll"] is True


def test_an_unknown_parameter_is_refused(signed_in: TestClient) -> None:
    answer = signed_in.patch(
        "/api/v1/interfaces/1/obfuscation", json={"obfuscation": {"Itime": 60}}
    )
    assert answer.status_code == 422
