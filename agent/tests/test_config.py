"""Settings: what the environment is allowed to say, and what it may not."""

from __future__ import annotations

from ipaddress import ip_network

import pytest
from pydantic import ValidationError

from awg_agent.config import LOOPBACK, Settings

TOKEN = "0123456789abcdef0123456789abcdef"


def test_token_is_required() -> None:
    with pytest.raises(ValidationError):
        Settings()


def test_short_token_is_refused() -> None:
    with pytest.raises(ValidationError):
        Settings(token="short")


def test_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWG_KEEPER_TOKEN", TOKEN)
    monkeypatch.setenv("AWG_KEEPER_PORT", "9000")
    settings = Settings()
    assert settings.port == 9000
    assert settings.awg_bin == "awg"


def test_unknown_variable_is_a_typo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWG_KEEPER_TOKEN", TOKEN)
    monkeypatch.setenv("AWG_KEEPER_PROT", "9000")
    with pytest.raises(ValidationError):
        Settings()


def test_subnets_and_interfaces_are_comma_separated() -> None:
    settings = Settings(
        token=TOKEN,
        allowed_subnets="10.0.0.0/8, 172.30.0.0/24",
        interfaces="awg0,awg1",
    )
    assert settings.allowed_subnets == [
        ip_network("10.0.0.0/8"),
        ip_network("172.30.0.0/24"),
    ]
    assert settings.interfaces == ["awg0", "awg1"]


def test_a_bad_cidr_fails_at_start_up() -> None:
    with pytest.raises(ValidationError):
        Settings(token=TOKEN, allowed_subnets="10.0.0.0/33")


def test_no_subnets_means_loopback_only() -> None:
    assert Settings(token=TOKEN).reachable_from() == LOOPBACK


def test_log_level_is_checked() -> None:
    assert Settings(token=TOKEN, log_level="debug").log_level == "DEBUG"
    with pytest.raises(ValidationError):
        Settings(token=TOKEN, log_level="chatty")
