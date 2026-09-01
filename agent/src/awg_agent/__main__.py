"""Run the agent in the foreground, the way the systemd unit does."""

from __future__ import annotations

import sys

import uvicorn
from pydantic import ValidationError

from awg_agent.app import create_app
from awg_agent.config import Settings


def main() -> int:
    """Read the environment, build the app, serve it. Non-zero on bad settings."""
    try:
        settings = Settings()
    except ValidationError as exc:
        print(f"awg-keeper agent: bad configuration\n{exc}", file=sys.stderr)
        return 2

    uvicorn.run(
        create_app(settings),
        host=settings.bind,
        port=settings.port,
        log_config=None,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
