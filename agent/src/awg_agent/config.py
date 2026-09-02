"""Settings the agent reads from its environment at start up.

systemd supplies them through EnvironmentFile=/etc/awg-keeper/agent.env, which
is mode 0600 because AWG_KEEPER_TOKEN is in it. There is no configuration file
and no default token: a service that manages a tunnel does not get to start
unauthenticated.
"""

from __future__ import annotations

import os
from ipaddress import IPv4Network, IPv6Network, ip_network
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

TOKEN_MIN = 32
LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})

Network = IPv4Network | IPv6Network

# Reachable when ALLOWED_SUBNETS is empty. Refusing everything would make an
# unset variable indistinguishable from a broken deployment; loopback keeps a
# local curl working and still publishes nothing.
LOOPBACK: tuple[Network, ...] = (ip_network("127.0.0.0/8"), ip_network("::1/128"))


def _split(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Everything the agent needs to know, all of it from the environment."""

    model_config = SettingsConfigDict(env_prefix="AWG_KEEPER_", extra="forbid")

    token: str = Field(min_length=TOKEN_MIN)
    bind: str = "127.0.0.1"
    port: int = Field(default=8081, ge=1, le=65535)
    allowed_subnets: Annotated[list[Network], NoDecode] = []
    interfaces: Annotated[list[str], NoDecode] = []
    awg_bin: str = "awg"
    awg_conf_dir: Path = Path("/etc/amnezia/amneziawg")
    xray_bin: str = "xray"
    xray_api: str = "127.0.0.1:10085"
    xray_config: Path = Path("/usr/local/etc/xray/config.json")
    command_timeout: float = Field(default=10.0, gt=0)
    log_level: str = "INFO"
    docs: bool = False

    @field_validator("allowed_subnets", mode="before")
    @classmethod
    def _networks(cls, value: str | list[str]) -> list[Network]:
        networks = []
        for item in _split(value):
            try:
                networks.append(ip_network(item, strict=False))
            except ValueError as exc:
                raise ValueError(f"not a CIDR: {item!r}: {exc}") from exc
        return networks

    @field_validator("interfaces", mode="before")
    @classmethod
    def _names(cls, value: str | list[str]) -> list[str]:
        return _split(value)

    @field_validator("log_level", mode="before")
    @classmethod
    def _level(cls, value: str) -> str:
        level = str(value).strip().upper()
        if level not in LOG_LEVELS:
            known = ", ".join(sorted(LOG_LEVELS))
            raise ValueError(f"unknown log level {value!r}; one of {known}")
        return level

    @model_validator(mode="after")
    def _no_unknown_variables(self) -> Settings:
        """Refuse a misspelled variable rather than ignoring it.

        pydantic-settings drops an environment variable that maps to no field,
        so AWG_KEEPER_ALOWED_SUBNETS would leave the allowlist empty and say
        nothing about it.
        """
        known = {f"AWG_KEEPER_{name}".upper() for name in type(self).model_fields}
        unknown = sorted(
            name
            for name in os.environ
            if name.upper().startswith("AWG_KEEPER_") and name.upper() not in known
        )
        if unknown:
            raise ValueError(f"unknown settings: {', '.join(unknown)}")
        return self

    def reachable_from(self) -> tuple[Network, ...]:
        """Which sources the API answers, with the empty case spelled out."""
        return tuple(self.allowed_subnets) or LOOPBACK
