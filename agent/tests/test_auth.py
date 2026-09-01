"""The two gates: the pre-set token, and the pre-set source subnets."""

from __future__ import annotations

from conftest import SOURCE, TOKEN
from fastapi.testclient import TestClient

from awg_agent.app import create_app
from awg_agent.config import Settings


def test_health_needs_nothing(client: TestClient) -> None:
    del client.headers["Authorization"]
    answer = client.get("/v1/health")
    assert answer.status_code == 200
    assert answer.json()["awg"].startswith("amneziawg-tools")


def test_a_missing_token_is_refused(client: TestClient) -> None:
    del client.headers["Authorization"]
    answer = client.get("/v1/state")
    assert answer.status_code == 401
    assert answer.headers["WWW-Authenticate"] == "Bearer"


def test_a_wrong_token_is_refused(client: TestClient) -> None:
    answer = client.get("/v1/state", headers={"Authorization": f"Bearer {TOKEN[:-1]}x"})
    assert answer.status_code == 401


def test_a_non_bearer_scheme_is_refused(client: TestClient) -> None:
    answer = client.get("/v1/state", headers={"Authorization": f"Basic {TOKEN}"})
    assert answer.status_code == 401


def test_a_source_outside_the_subnets_is_refused(settings: Settings) -> None:
    with TestClient(create_app(settings), client=("10.9.9.9", 4000)) as outsider:
        answer = outsider.get("/v1/state", headers={"Authorization": f"Bearer {TOKEN}"})
    assert answer.status_code == 403


def test_a_forwarded_header_does_not_move_the_source(settings: Settings) -> None:
    with TestClient(create_app(settings), client=("10.9.9.9", 4000)) as outsider:
        answer = outsider.get(
            "/v1/state",
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "X-Forwarded-For": SOURCE[0],
            },
        )
    assert answer.status_code == 403
