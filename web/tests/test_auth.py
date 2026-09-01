"""Signing in, staying in, and being kept out."""

from __future__ import annotations

from ipaddress import ip_network

import pytest
from conftest import PASSWORD, USER
from fastapi.testclient import TestClient

from awg_panel.app import create_app
from awg_panel.config import Settings


def test_sign_in_and_out(client: TestClient) -> None:
    answer = client.post(
        "/api/v1/auth/login", json={"user": USER, "password": PASSWORD}
    )
    assert answer.status_code == 200
    assert answer.json()["user"] == USER
    assert client.cookies.get("awg_session")

    assert client.get("/api/v1/auth/me").json()["user"] == USER
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_a_wrong_password_is_refused(client: TestClient) -> None:
    answer = client.post("/api/v1/auth/login", json={"user": USER, "password": "no"})
    assert answer.status_code == 401
    assert not client.cookies.get("awg_session")


def test_no_session_is_401(client: TestClient) -> None:
    assert client.get("/api/v1/profiles").status_code == 401


def test_ping_needs_nothing(client: TestClient) -> None:
    assert client.get("/api/v1/ping").json()["status"] == "ok"


def test_a_write_without_the_csrf_token_is_403(signed_in: TestClient) -> None:
    del signed_in.headers["X-CSRF-Token"]
    answer = signed_in.post(
        "/api/v1/profiles",
        json={"name": "a", "interface_id": 1, "public_key": "a" * 43 + "="},
    )
    assert answer.status_code == 403


def test_repeated_failures_lock_the_account_out(client: TestClient) -> None:
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"user": USER, "password": "no"})
    answer = client.post(
        "/api/v1/auth/login", json={"user": USER, "password": PASSWORD}
    )
    assert answer.status_code == 429


def test_a_source_outside_the_subnets_is_refused(
    settings: Settings,
    node: None,
) -> None:
    settings.allowed_subnets = [ip_network("10.0.0.0/8")]
    with TestClient(
        create_app(settings), base_url="https://testserver", client=("192.0.2.5", 1)
    ) as outsider:
        answer = outsider.post(
            "/api/v1/auth/login", json={"user": USER, "password": PASSWORD}
        )
    assert answer.status_code == 403


@pytest.fixture(autouse=True)
def _reset_lockout() -> None:
    """Clear the lockout counter, which is process-wide, before each test."""
    from awg_panel import auth

    auth._failures.clear()
