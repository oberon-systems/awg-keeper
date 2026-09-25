"""The only module that starts a process.

Always an argv list, never a shell: every caller passes values that came off
the network, and `shell=True` here would make the rest of the package a remote
command execution surface no amount of validation elsewhere could close.
"""

from __future__ import annotations

import logging
import subprocess

LOG = logging.getLogger(__name__)


class CommandError(RuntimeError):
    """A tool exited non-zero, timed out, or was not on PATH at all."""

    def __init__(self, argv: list[str], reason: str, stderr: str = "") -> None:
        """Keep argv and stderr apart, so only the former can be echoed back."""
        super().__init__(f"{argv[0]}: {reason}")
        self.argv = argv
        self.reason = reason
        self.stderr = stderr


def run(
    argv: list[str],
    timeout: float = 10.0,
    secret: str | None = None,
    stdin: str | None = None,
) -> str:
    """Run a command and return its stdout, raising CommandError otherwise."""
    # The secret still reaches the process; only the log and the error lose it.
    shown = [("***" if secret and item == secret else item) for item in argv]
    LOG.debug("running %s", shown)
    try:
        done = subprocess.run(
            argv,
            capture_output=True,
            check=False,
            input=stdin,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise CommandError(shown, "not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise CommandError(shown, f"timed out after {timeout}s") from exc

    if done.returncode != 0:
        stderr = done.stderr.strip()
        LOG.error("%s exited %d: %s", argv[0], done.returncode, stderr)
        raise CommandError(shown, f"exited {done.returncode}", stderr)

    return done.stdout
