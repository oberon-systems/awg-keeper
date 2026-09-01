"""Fixtures: a temporary database, a stub agent, and a signed-in client.

Nothing here reaches a node or a container. The schema is created from the
models rather than through alembic: the migration is asserted separately, and
every other test wants a database, not a migration run.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from awg_panel import agent
from awg_panel.app import create_app
from awg_panel.auth import hash_password
from awg_panel.config import Settings
from awg_panel.models import Interface, Node

SECRET = "0123456789abcdef0123456789abcdef"
USER = "admin"
PASSWORD = "correct horse battery staple"
SOURCE = ("127.0.0.1", 40000)

OBFUSCATION = {"Jc": 4, "Jmin": 50, "Jmax": 1000, "S1": 86, "S2": 574, "H1": 1077035230}


class StubAgent:
    """Records what the panel asked the node to do, and can be told to fail."""

    def __init__(self) -> None:
        """Start with an empty call log and a node that accepts everything."""
        self.calls: list[tuple[Any, ...]] = []
        self.fail = False
        self.peers: list[str] = []

    def add_peer(
        self,
        settings: Settings,
        interface: str,
        public_key: str,
        allowed_ips: list[str],
        keepalive: int | None = None,
    ) -> dict[str, Any]:
        """Stand in for a POST to the agent."""
        if self.fail:
            raise agent.AgentError("the agent is unreachable")
        self.calls.append(("add", interface, public_key, tuple(allowed_ips)))
        self.peers.append(public_key)
        return {"public_key": public_key, "allowed_ips": allowed_ips}

    def remove_peer(
        self,
        settings: Settings,
        interface: str,
        public_key: str,
    ) -> None:
        """Stand in for a DELETE to the agent."""
        if self.fail:
            raise agent.AgentError("the agent is unreachable")
        self.calls.append(("remove", interface, public_key))
        if public_key in self.peers:
            self.peers.remove(public_key)

    def state(self, settings: Settings) -> dict[str, Any]:
        """Stand in for GET /v1/state."""
        if self.fail:
            raise agent.AgentError("the agent is unreachable")
        return {
            "interfaces": [
                {
                    "name": "awg-mgmt",
                    "peers": [{"public_key": key} for key in self.peers],
                }
            ],
            "inbounds": [],
        }


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a developer's own AWG_PANEL_* out of the suite."""
    for name in list(os.environ):
        if name.startswith("AWG_PANEL_"):
            monkeypatch.delenv(name)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Build settings against a database of this test's own."""
    return Settings(
        secret_key=SECRET,
        admin_user=USER,
        admin_password_hash=hash_password(PASSWORD),
        database_path=tmp_path / "panel.sqlite",
        agent_token="a-token",
        static_dir=tmp_path / "absent-static",
    )


@pytest.fixture
def node(settings: Settings) -> None:
    """Seed the one node and its interface, the way a deployment would."""
    from awg_panel.db import build_engine

    engine = build_engine(settings)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        row = Node(name="gateway", endpoint="http://127.0.0.1:8081")
        session.add(row)
        session.flush()
        session.add(
            Interface(
                node_id=int(row.id or 0),
                name="awg-mgmt",
                listen_port=51820,
                address="10.8.0.1/24",
                pool="10.8.0.0/24",
                server_public_key="c" * 43 + "=",
                endpoint_host="vpn.example",
                dns="10.8.0.1",
                mtu=1280,
                obfuscation=OBFUSCATION,
            )
        )
        session.commit()


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> StubAgent:
    """Put the stub in place of the real agent client."""
    stand_in = StubAgent()
    monkeypatch.setattr(agent, "add_peer", stand_in.add_peer)
    monkeypatch.setattr(agent, "remove_peer", stand_in.remove_peer)
    monkeypatch.setattr(agent, "state", stand_in.state)
    return stand_in


@pytest.fixture
def client(settings: Settings, node: None, stub: StubAgent) -> Iterator[TestClient]:
    """Build an anonymous client, from an address the settings allow."""
    # https, because the session cookie is Secure: a browser would not send
    # it back over plain http and neither does the test client.
    with TestClient(
        create_app(settings), base_url="https://testserver", client=SOURCE
    ) as test_client:
        yield test_client


@pytest.fixture
def signed_in(client: TestClient) -> TestClient:
    """Sign in, and carry the CSRF token on every write after that."""
    answer = client.post(
        "/api/v1/auth/login", json={"user": USER, "password": PASSWORD}
    )
    assert answer.status_code == 200
    client.headers.update({"X-CSRF-Token": client.cookies.get("awg_csrf", "")})
    return client
