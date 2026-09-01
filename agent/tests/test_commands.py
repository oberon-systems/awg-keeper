"""The one module that starts a process."""

from __future__ import annotations

import pytest

from awg_agent.commands import CommandError, run


def test_returns_stdout() -> None:
    assert run(["/bin/echo", "hello"]).strip() == "hello"


def test_a_missing_binary_is_a_command_error() -> None:
    with pytest.raises(CommandError) as caught:
        run(["/nonexistent/awg", "show"])
    assert "not found" in caught.value.reason


def test_a_non_zero_exit_carries_the_stderr() -> None:
    with pytest.raises(CommandError) as caught:
        run(["/bin/sh", "-c", "echo boom >&2; exit 3"])
    assert caught.value.stderr == "boom"
    assert "exited 3" in caught.value.reason


def test_a_timeout_is_a_command_error() -> None:
    with pytest.raises(CommandError) as caught:
        run(["/bin/sleep", "5"], timeout=0.1)
    assert "timed out" in caught.value.reason


def test_arguments_are_never_a_shell() -> None:
    # The value is a whole argument, not two commands.
    assert run(["/bin/echo", "a; touch /tmp/pwned"]).strip() == "a; touch /tmp/pwned"
