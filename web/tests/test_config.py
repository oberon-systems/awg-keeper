"""Settings: what the environment is allowed to say, and what it may not."""

from __future__ import annotations

from ipaddress import ip_network
from pathlib import Path

import pytest
from pydantic import ValidationError

from awg_panel.config import Settings

SECRET = "0123456789abcdef0123456789abcdef"
HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHQ$0000000000000000000000000000"


def test_the_secret_and_the_hash_are_required() -> None:
    with pytest.raises(ValidationError):
        Settings()


def test_a_short_secret_is_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(secret_key="short", admin_password_hash=HASH)


def test_subnets_are_comma_separated() -> None:
    settings = Settings(
        secret_key=SECRET,
        admin_password_hash=HASH,
        allowed_subnets="10.0.0.0/8, 192.168.0.0/16",
    )
    assert settings.allowed_subnets == [
        ip_network("10.0.0.0/8"),
        ip_network("192.168.0.0/16"),
    ]


def test_the_database_url_follows_the_path(tmp_path: Path) -> None:
    settings = Settings(
        secret_key=SECRET,
        admin_password_hash=HASH,
        database_path=tmp_path / "panel.sqlite",
    )
    assert settings.database_url == f"sqlite:///{tmp_path / 'panel.sqlite'}"


def test_an_unknown_variable_is_a_typo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWG_PANEL_SECRET_KEY", SECRET)
    monkeypatch.setenv("AWG_PANEL_ADMIN_PASSWORD_HASH", HASH)
    monkeypatch.setenv("AWG_PANEL_ADMIN_USR", "root")
    with pytest.raises(ValidationError):
        Settings()


def test_the_agent_url_is_no_longer_a_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWG_PANEL_SECRET_KEY", SECRET)
    monkeypatch.setenv("AWG_PANEL_ADMIN_PASSWORD_HASH", HASH)
    monkeypatch.setenv("AWG_PANEL_AGENT_URL", "http://127.0.0.1:8081")
    with pytest.raises(ValidationError, match="AWG_PANEL_AGENT_URL"):
        Settings()


def test_the_agents_come_from_one_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWG_PANEL_SECRET_KEY", SECRET)
    monkeypatch.setenv("AWG_PANEL_ADMIN_PASSWORD_HASH", HASH)
    monkeypatch.setenv(
        "AWG_PANEL_AGENTS",
        "gw-01=http://192.168.201.1:3000/, gw-02=https://10.0.0.2:3000",
    )
    assert Settings().agents == {
        "gw-01": "http://192.168.201.1:3000",
        "gw-02": "https://10.0.0.2:3000",
    }


@pytest.mark.parametrize(
    "value", ["gw-01", "gw-01=192.168.201.1:3000", "a=http://x,a=http://y"]
)
def test_a_malformed_agent_list_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("AWG_PANEL_SECRET_KEY", SECRET)
    monkeypatch.setenv("AWG_PANEL_ADMIN_PASSWORD_HASH", HASH)
    monkeypatch.setenv("AWG_PANEL_AGENTS", value)
    with pytest.raises(ValidationError):
        Settings()
