"""The migrations and the models must describe the same schema.

Matching table names catches a model nobody migrated; running the chain on a
database from the previous release catches a migration that only works empty.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlmodel import SQLModel

from awg_panel import models  # noqa: F401
from awg_panel.auth import hash_password

WEB = Path(__file__).resolve().parents[1]
VERSIONS = sorted((WEB / "migrations/versions").glob("0*.py"))
CREATED = r'op\.create_table\(\n\s+"([a-z_]+)"'
DROPPED = r'op\.drop_table\("([a-z_]+)"\)'


def _all(pattern: str) -> set[str]:
    return {name for path in VERSIONS for name in re.findall(pattern, path.read_text())}


def test_every_model_table_is_created_by_the_migrations() -> None:
    assert set(SQLModel.metadata.tables) == _all(CREATED)


def test_the_migrations_drop_what_they_create() -> None:
    assert _all(CREATED) == _all(DROPPED)


def _alembic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Config, Path]:
    database = tmp_path / "panel.sqlite"
    monkeypatch.setenv("AWG_PANEL_SECRET_KEY", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("AWG_PANEL_ADMIN_PASSWORD_HASH", hash_password("x"))
    monkeypatch.setenv("AWG_PANEL_DATABASE_PATH", str(database))
    # No ini file: its logging section would disable the loggers other tests capture.
    config = Config()
    config.set_main_option("script_location", str(WEB / "migrations"))
    return config, database


def test_an_interface_from_0_2_0_survives_as_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, database = _alembic(tmp_path, monkeypatch)
    command.upgrade(config, "0001")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO node (id, name, endpoint, status, created_at) "
            "VALUES (1, 'gw', 'http://127.0.0.1:3000', 'unknown', '2026-09-01')"
        )
        connection.execute(
            "INSERT INTO interface (node_id, name, listen_port, address, pool, "
            "server_public_key, endpoint_host, client_allowed_ips) VALUES "
            "(1, 'awg0', 51820, '10.8.0.1/24', '10.8.0.0/24', 'k', 'vpn', '0.0.0.0/0')"
        )

    command.upgrade(config, "head")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT enabled FROM interface").fetchall() == [(1,)]
        connection.execute(
            "INSERT INTO interface (node_id, name, listen_port, server_public_key, "
            "client_allowed_ips, enabled) "
            "VALUES (1, 'awg1', 51821, 'k', '0.0.0.0/0', 0)"
        )

    command.downgrade(config, "base")
