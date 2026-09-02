"""Settings the panel reads from its environment at start up.

Compose supplies them; nothing is read from a file. The admin password is held
as an argon2id hash, so the plaintext exists only in whatever minted it.
"""

from __future__ import annotations

import os
from ipaddress import IPv4Network, IPv6Network, ip_network
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

SECRET_MIN = 32
LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})

Network = IPv4Network | IPv6Network


def _split(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Everything the panel needs, all of it from the environment."""

    model_config = SettingsConfigDict(env_prefix="AWG_PANEL_", extra="forbid")

    # Signs the session cookie. Rotating it logs everybody out, which is the
    # only way to revoke a session the panel does not otherwise track.
    secret_key: str = Field(min_length=SECRET_MIN)
    admin_user: str = "admin"
    admin_password_hash: str

    bind: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    # Empty means every source, which is what a reverse proxy in front of the
    # panel makes true anyway.
    allowed_subnets: Annotated[list[Network], NoDecode] = []

    database_path: Path = Path("/var/lib/awg-keeper/panel.sqlite")
    session_ttl: int = Field(default=43200, gt=0)
    # The cookies are Secure by default, so a browser will not send them back
    # over plain http. Only a local run without a proxy in front turns it off.
    cookie_secure: bool = True
    login_attempts: int = Field(default=5, gt=0)
    lockout_seconds: int = Field(default=300, gt=0)

    agent_url: str = "http://127.0.0.1:8081"
    agent_token: str = ""
    agent_timeout: float = Field(default=10.0, gt=0)

    static_dir: Path = Path("/app/static")
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
        so AWG_PANEL_ALOWED_SUBNETS would leave the allowlist empty and say
        nothing about it.
        """
        known = {f"AWG_PANEL_{name}".upper() for name in type(self).model_fields}
        unknown = sorted(
            name
            for name in os.environ
            if name.upper().startswith("AWG_PANEL_") and name.upper() not in known
        )
        if unknown:
            raise ValueError(f"unknown settings: {', '.join(unknown)}")
        return self

    @property
    def database_url(self) -> str:
        """The SQLAlchemy URL, which alembic and the app both build from."""
        return f"sqlite:///{self.database_path}"
