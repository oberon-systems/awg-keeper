"""Provisioning: the block it prints has to be one the panel accepts."""

from __future__ import annotations

import pytest
from argon2 import PasswordHasher

from awg_panel.config import SECRET_MIN, Settings
from awg_panel.provision import TOKEN_MIN, main


def _env(out: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in out.splitlines() if line)


def test_every_setting_the_panel_requires_is_minted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["awg-panel-secrets"])
    assert main() == 0

    env = _env(capsys.readouterr().out)
    settings = Settings(
        secret_key=env["AWG_PANEL_SECRET_KEY"],
        admin_user=env["AWG_PANEL_ADMIN_USER"],
        admin_password_hash=env["AWG_PANEL_ADMIN_PASSWORD_HASH"],
    )
    assert settings.admin_user == "admin"
    assert len(env["AWG_PANEL_SECRET_KEY"]) >= SECRET_MIN
    assert len(env["AWG_PANEL_AGENT_TOKEN"]) >= TOKEN_MIN


def test_the_printed_password_verifies_against_the_printed_hash(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["awg-panel-secrets"])
    assert main() == 0

    captured = capsys.readouterr()
    password = captured.err.splitlines()[0].removeprefix("admin password: ")
    hash_ = _env(captured.out)["AWG_PANEL_ADMIN_PASSWORD_HASH"]

    assert PasswordHasher().verify(hash_, password)


def test_a_typed_password_is_never_printed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["awg-panel-secrets", "--ask"])
    monkeypatch.setattr("awg_panel.provision.getpass", lambda _: "typed-secret")
    assert main() == 0

    captured = capsys.readouterr()
    assert "typed-secret" not in captured.err
    hash_ = _env(captured.out)["AWG_PANEL_ADMIN_PASSWORD_HASH"]

    assert PasswordHasher().verify(hash_, "typed-secret")


def test_two_different_passwords_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(["one", "two"])
    monkeypatch.setattr("sys.argv", ["awg-panel-secrets", "--ask"])
    monkeypatch.setattr("awg_panel.provision.getpass", lambda _: next(answers))

    with pytest.raises(SystemExit):
        main()
