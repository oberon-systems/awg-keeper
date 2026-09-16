"""What the panel writes to its log, and what it never does."""

from __future__ import annotations

import logging

import pytest
from conftest import PASSWORD, SECRET, SOURCE, StubAgent
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from awg_panel.app import create_app
from awg_panel.config import Settings
from awg_panel.db import build_engine


def _messages(caplog: pytest.LogCaptureFixture, name: str) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == name]


def test_the_healthcheck_is_logged(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    client.get("/api/v1/ping")
    lines = _messages(caplog, "awg_panel.access")
    assert lines[-1].startswith("GET /api/v1/ping 200 ")
    assert lines[-1].endswith(f"from {SOURCE[0]}")


def test_signing_in_logs_no_secret(
    signed_in: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    signed_in.get("/api/v1/profiles")
    assert PASSWORD not in caplog.text
    assert SECRET not in caplog.text
    assert "a-token" not in caplog.text


def test_the_start_counts_nodes_and_interfaces(
    settings: Settings,
    node: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    create_app(settings)
    assert "1 nodes, 1 interfaces" in _messages(caplog, "awg_panel.app")


def test_the_start_warns_about_an_empty_database(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    SQLModel.metadata.create_all(build_engine(settings))
    create_app(settings)
    assert "no nodes or no interfaces: profiles cannot be issued until added" in (
        _messages(caplog, "awg_panel.app")
    )


def test_a_down_agent_is_logged(
    signed_in: TestClient,
    stub: StubAgent,
    caplog: pytest.LogCaptureFixture,
) -> None:
    stub.fail = True
    signed_in.get("/api/v1/agents")
    assert "agent gateway is down: gateway is unreachable: ConnectError()" in (
        _messages(caplog, "awg_panel.service")
    )


def test_an_unexpected_error_is_logged_with_its_traceback(
    settings: Settings,
    node: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(settings)
    broken = APIRouter()

    @broken.get("/api/v1/broken")
    def fail() -> None:
        raise PermissionError("denied")

    app.include_router(broken)
    with TestClient(
        app,
        base_url="https://testserver",
        client=SOURCE,
        raise_server_exceptions=False,
    ) as test_client:
        answer = test_client.get("/api/v1/broken")

    assert answer.status_code == 500
    assert "denied" not in answer.text
    errors = [r for r in caplog.records if r.name == "awg_panel.app" and r.exc_info]
    assert errors and "GET /api/v1/broken" in errors[0].getMessage()
