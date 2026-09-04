"""Mint everything the panel needs before its first start.

The admin password is the only value a person ever types, so it is the only one
this prints on its own - and it prints it once, because the panel keeps the
argon2id hash and nothing anywhere can give the plaintext back.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from getpass import getpass

from awg_panel.auth import hash_password
from awg_panel.config import SECRET_MIN

# awg_agent.config.TOKEN_MIN, restated rather than imported: the agent is a
# separate package and the panel image does not ship it.
TOKEN_MIN = 32

PASSWORD_BYTES = 18


def _typed_password() -> str:
    """Ask for the admin password twice and return it."""
    first = getpass("admin password: ")
    if not first:
        raise SystemExit("awg-keeper panel: an empty password is not one")
    if first != getpass("repeat: "):
        raise SystemExit("awg-keeper panel: the two passwords differ")
    return first


def main() -> int:
    """Write an .env block to stdout, and a generated password to stderr."""
    parser = argparse.ArgumentParser(
        prog="awg-panel-secrets",
        description=(
            "Mint the panel's secrets: session key, admin password hash, agent token."
        ),
    )
    parser.add_argument(
        "--ask",
        action="store_true",
        help="type the admin password instead of generating one",
    )
    parser.add_argument(
        "--user",
        default="admin",
        help="name of the admin account (default: admin)",
    )
    args = parser.parse_args()

    if args.ask:
        password = _typed_password()
    else:
        password = secrets.token_urlsafe(PASSWORD_BYTES)
        # stderr, so `make secrets > .env` still shows the password.
        print(f"admin password: {password}", file=sys.stderr)
        print("Keep it. Nothing below can give it back.", file=sys.stderr)

    print(f"AWG_PANEL_SECRET_KEY={secrets.token_hex(SECRET_MIN)}")
    print(f"AWG_PANEL_ADMIN_USER={args.user}")
    print(f"AWG_PANEL_ADMIN_PASSWORD_HASH={hash_password(password)}")
    print(f"AWG_PANEL_AGENT_TOKEN={secrets.token_hex(TOKEN_MIN)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
