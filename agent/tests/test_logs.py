"""What the agent writes to its log, and what it never does."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from conftest import SERVER_KEY, SOURCE, TOKEN, argv_log
from fastapi import APIRouter
from fastapi.testclient import TestClient

from awg_agent.app import create_app
from awg_agent.config import Settings


def _messages(caplog: pytest.LogCaptureFixture, name: str) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == name]


def test_every_request_is_logged_without_the_token(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    client.get("/v1/health")
    client.get("/v1/state")

    lines = _messages(caplog, "awg_agent.access")
    assert lines[0].startswith("GET /v1/health 200 ")
    assert lines[0].endswith(f"from {SOURCE[0]}")
    assert lines[1].startswith("GET /v1/state 200 ")
    assert TOKEN not in caplog.text


def test_the_start_is_logged_without_the_token(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    create_app(settings)
    started = _messages(caplog, "awg_agent.app")
    assert "interfaces awg0" in started[0]
    assert started[1] == "awg: amneziawg-tools v1.0.20241018"
    assert started[2].startswith("xray: Xray 1.8.24")
    assert TOKEN not in caplog.text


def test_the_start_checks_every_interface(
    settings: Settings,
    host: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    create_app(settings)
    assert _messages(caplog, "awg_agent.awg") == [
        f"awg0: up, listen_port 51820, public_key {SERVER_KEY}, 1 peers"
    ]
    assert not [line for line in argv_log(host) if "private-key" in line]


def test_the_start_names_an_absent_interface_as_an_error(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    wider = settings.model_copy(update={"interfaces": ["awg0", "awg9"]})
    create_app(wider)
    errors = [
        r.getMessage()
        for r in caplog.records
        if r.name == "awg_agent.awg" and r.levelno == logging.ERROR
    ]
    assert errors == ["awg9: absent, not listed by awg"]


def test_the_start_says_when_awg_is_unusable(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("FAKE_AWG_FAIL", "1")
    create_app(settings)
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any(line.startswith("awg at ") for line in errors)
    assert (
        "awg failed: exited 1: awg: RTNETLINK answers: Operation not permitted"
        in errors
    )


def test_status_logs_only_what_changed(
    client: TestClient,
    host: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    caplog.clear()
    client.get("/v1/status")
    client.get("/v1/status")
    assert _messages(caplog, "awg_agent.awg") == []

    state = json.loads((host / "awg-state.json").read_text(encoding="utf-8"))
    state["awg1"] = state.pop("awg0")
    (host / "awg-state.json").write_text(json.dumps(state), encoding="utf-8")
    client.get("/v1/status")
    client.get("/v1/status")
    assert _messages(caplog, "awg_agent.awg") == ["awg0: absent, not listed by awg"]


def test_a_refused_token_is_logged(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client.get("/v1/state", headers={"Authorization": "Bearer wrong"})
    assert f"refused {SOURCE[0]}: bad token" in _messages(caplog, "awg_agent.auth")


def test_a_configured_interface_awg_does_not_list_is_logged(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    wider = settings.model_copy(update={"interfaces": ["awg0", "awg9"]})
    with TestClient(create_app(wider), client=SOURCE) as test_client:
        test_client.get("/v1/state", headers={"Authorization": f"Bearer {TOKEN}"})
    assert "interface awg9 is configured but awg does not list it" in _messages(
        caplog, "awg_agent.awg"
    )


def test_an_unexpected_error_is_logged_with_its_traceback(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(settings)
    broken = APIRouter()

    @broken.get("/v1/broken")
    def fail() -> None:
        raise PermissionError("denied")

    app.include_router(broken)
    with TestClient(app, client=SOURCE, raise_server_exceptions=False) as test_client:
        answer = test_client.get("/v1/broken")

    assert answer.status_code == 500
    assert "denied" not in answer.text
    errors = [r for r in caplog.records if r.name == "awg_agent.app" and r.exc_info]
    assert errors and "GET /v1/broken" in errors[0].getMessage()
    assert "GET /v1/broken 500 " in " ".join(_messages(caplog, "awg_agent.access"))
