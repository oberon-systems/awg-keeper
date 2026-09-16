"""What the agent writes to its log, and what it never does."""

from __future__ import annotations

import logging

import pytest
from conftest import SOURCE, TOKEN
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
    assert len(started) == 1
    assert "interfaces awg0" in started[0]
    assert TOKEN not in caplog.text


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
