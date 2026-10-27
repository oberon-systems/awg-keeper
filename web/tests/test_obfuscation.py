"""The obfuscation of an interface: kept by the panel, pushed back on drift."""

from __future__ import annotations

import pytest
from conftest import OBFUSCATION, StubAgent
from fastapi.testclient import TestClient
from sqlmodel import Session

from awg_panel import agent
from awg_panel.config import Settings
from awg_panel.db import build_engine
from awg_panel.models import Interface

KEY = "a" * 43 + "="
HEADER_KEY = "h" * 43 + "="


def _live(**changed: str) -> dict[str, str]:
    live = {
        "jc": "4",
        "jmin": "50",
        "jmax": "1000",
        "s1": "86",
        "s2": "574",
        "h1": "1077035230",
    }
    return {**live, **changed}


def _stored(settings: Settings) -> dict[str, object]:
    with Session(build_engine(settings)) as session:
        row = session.get(Interface, 1)
        assert row is not None
        return dict(row.obfuscation)


def test_a_drifted_interface_gets_the_panel_config_back(
    signed_in: TestClient, stub: StubAgent, settings: Settings
) -> None:
    stub.obfuscations["awg-mgmt"] = _live(
        jc="5", **{"header-protection-key": HEADER_KEY}
    )
    agents = signed_in.post("/api/v1/agents/probe").json()
    assert ("set_obfuscation", "gateway", "awg-mgmt", {"jc": "4"}) in stub.calls
    assert _stored(settings) == OBFUSCATION
    found = agents[0]["interfaces"][0]
    assert found["obfuscation"] == OBFUSCATION
    assert found["drift"] == ["Jc", "HeaderProtectionKey"]
    assert "HeaderProtectionKey" in found["drift_error"]


def test_a_matching_interface_is_left_alone(
    signed_in: TestClient, stub: StubAgent
) -> None:
    stub.obfuscations["awg-mgmt"] = _live()
    agents = signed_in.post("/api/v1/agents/probe").json()
    assert not [call for call in stub.calls if call[0] == "set_obfuscation"]
    assert agents[0]["interfaces"][0]["drift"] == []


def test_a_failed_restore_is_reported_and_keeps_the_panel_config(
    signed_in: TestClient, stub: StubAgent, settings: Settings
) -> None:
    stub.obfuscations["awg-mgmt"] = _live(jc="5")
    stub.fail_obfuscation = True
    agents = signed_in.post("/api/v1/agents/probe").json()
    assert "not persisted" in agents[0]["interfaces"][0]["drift_error"]
    assert _stored(settings) == OBFUSCATION


def test_an_old_agent_is_never_read_into_the_panel(
    signed_in: TestClient, stub: StubAgent, settings: Settings
) -> None:
    agents = signed_in.post("/api/v1/agents/probe").json()
    assert agents[0]["interfaces"][0]["obfuscation"] == OBFUSCATION
    assert _stored(settings) == OBFUSCATION
    assert not [call for call in stub.calls if call[0] == "set_obfuscation"]


def test_an_unwritable_conf_dir_degrades_the_agent(
    signed_in: TestClient, stub: StubAgent
) -> None:
    stub.conf_error = "/etc/amnezia/amneziawg is not writable by the agent"
    agents = signed_in.post("/api/v1/agents/probe").json()
    assert agents[0]["status"] == "degraded"
    assert "not writable" in agents[0]["error"]


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


def test_a_failed_edit_leaves_the_panel_config(
    signed_in: TestClient, stub: StubAgent, settings: Settings
) -> None:
    stub.fail_obfuscation = True
    answer = signed_in.patch(
        "/api/v1/interfaces/1/obfuscation", json={"obfuscation": {"Jc": 6}}
    )
    assert answer.status_code == 502
    assert "not persisted" in answer.json()["detail"]
    assert _stored(settings) == OBFUSCATION


def test_an_edit_applied_otherwise_is_refused(
    signed_in: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agent, "set_obfuscation", lambda *args: {"jc": "9"})
    answer = signed_in.patch(
        "/api/v1/interfaces/1/obfuscation", json={"obfuscation": {"Jc": 6}}
    )
    assert answer.status_code == 502
    assert "Jc" in answer.json()["detail"]
    assert _stored(settings) == OBFUSCATION


def test_an_import_takes_the_live_obfuscation_once(
    signed_in: TestClient, stub: StubAgent
) -> None:
    stub.extra.append(
        {"name": "awg-new", "present": True, "public_key": KEY, "listen_port": 51821}
    )
    stub.obfuscations["awg-new"] = {"jc": "3", "header-protection-key": HEADER_KEY}
    agents = signed_in.post("/api/v1/agents/probe").json()
    new = next(item for item in agents[0]["interfaces"] if item["name"] == "awg-new")
    edit = signed_in.patch(
        f"/api/v1/interfaces/{new['id']}/obfuscation", json={"obfuscation": {"Jc": 6}}
    )
    assert edit.status_code == 422
    assert "import it first" in edit.json()["detail"]

    path = f"/api/v1/interfaces/{new['id']}/obfuscation/import"
    imported = signed_in.post(path)
    assert imported.status_code == 200
    found = next(
        item for item in imported.json()["interfaces"] if item["name"] == "awg-new"
    )
    assert found["obfuscation"] == {"Jc": 3, "HeaderProtectionKey": HEADER_KEY}
    assert signed_in.post(path).status_code == 422


def test_an_unknown_parameter_is_refused(signed_in: TestClient) -> None:
    answer = signed_in.patch(
        "/api/v1/interfaces/1/obfuscation", json={"obfuscation": {"Itime": 60}}
    )
    assert answer.status_code == 422
