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


def run(argv: list[str], timeout: float = 10.0) -> str:
    """Run a command and return its stdout, raising CommandError otherwise."""
    LOG.debug("running %s", argv)
    try:
        done = subprocess.run(
            argv,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise CommandError(argv, "not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise CommandError(argv, f"timed out after {timeout}s") from exc

    if done.returncode != 0:
        stderr = done.stderr.strip()
        LOG.error("%s exited %d: %s", argv[0], done.returncode, stderr)
        raise CommandError(argv, f"exited {done.returncode}", stderr)

    return done.stdout
