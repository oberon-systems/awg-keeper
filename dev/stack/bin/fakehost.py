#!/usr/bin/env python3
"""Build the fake host the stand's agent manages: binaries, state, config.

The binaries are not written here. They are lifted out of
`agent/tests/conftest.py`, where the same stand-ins for awg, xray and ip
already exist for the unit tests, so the stand and the suite cannot drift into
disagreeing about what the host answers.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent.parent
CONFTEST = REPO_ROOT / "agent" / "tests" / "conftest.py"

# Constant in conftest.py -> file under host/bin/.
BINARIES = {"FAKE_AWG": "awg", "FAKE_XRAY": "xray", "FAKE_IP": "ip"}

SERVER_KEY_0 = "Kf8nQ2pLxvR7mZaT4uYcW1dEbHjNsG6iP0oXlV9rC3A="
SERVER_KEY_1 = "Tz5wB1yUqNfL8kJdR6sXoM2vHaE7cG0pIgZ4nQtY9mE="
PEER_A = "aQ7rT2nLpX8vK1mZcW5dYbH3jNsG6iF0oUlV9xC4eR8="
PEER_B = "bW3kY9tRqM5nL2pXcV8dZfH7jSsG1iB0oAlU6xE4wT2="
PEER_C = "cE6mU4pKrN9vL3qXdW7bZgH2jTsF5iC0oBlY8xA1yR7="

AWG_STATE = {
    "awg0": {
        "public_key": SERVER_KEY_0,
        "listen_port": 51820,
        "addresses": ["10.8.0.1/24"],
        "obfuscation": {
            "jc": "4",
            "jmin": "50",
            "jmax": "1000",
            "s1": "15",
            "s2": "36",
            "h1": "1077035230",
            "h2": "1439362799",
            "h3": "1152413886",
            "h4": "1826115271",
        },
        "peers": {
            PEER_A: {"allowed_ips": "10.8.0.2/32", "rx": 1048576, "tx": 2097152},
            PEER_B: {"allowed_ips": "10.8.0.3/32", "rx": 524288, "tx": 131072},
        },
    },
    "awg1": {
        "public_key": SERVER_KEY_1,
        "listen_port": 51821,
        "addresses": ["10.9.0.1/24"],
        "obfuscation": {"jc": "3", "jmin": "40", "jmax": "800"},
        "peers": {PEER_C: {"allowed_ips": "10.9.0.2/32", "rx": 0, "tx": 0}},
    },
}

XRAY_CONFIG = {
    "log": {"loglevel": "warning"},
    "api": {"tag": "api", "services": ["HandlerService"]},
    "inbounds": [
        {
            "tag": "reality-443",
            "listen": "0.0.0.0",
            "port": 443,
            "protocol": "vless",
            "settings": {
                "decryption": "none",
                "clients": [
                    {
                        "id": "6f1f0b8e-0b1a-4c2e-9d3f-5a6b7c8d9e01",
                        "email": "seed@ams-1",
                        "flow": "xtls-rprx-vision",
                    }
                ],
            },
            "streamSettings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {
                    "dest": "www.microsoft.com:443",
                    "serverNames": ["www.microsoft.com"],
                    "shortIds": ["0123456789abcdef"],
                },
            },
        }
    ],
    "outbounds": [{"tag": "direct", "protocol": "freedom"}],
}


def _sources(conftest: Path) -> dict[str, str]:
    """Read the three fake binaries out of the agent's test fixtures."""
    if not conftest.is_file():
        raise SystemExit(f"fakehost: {conftest} is missing")
    tree = ast.parse(conftest.read_text(encoding="utf-8"), filename=str(conftest))
    found: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            name = getattr(target, "id", None)
            if name in BINARIES and isinstance(node.value, ast.Constant):
                found[name] = str(node.value.value)
    missing = sorted(set(BINARIES) - set(found))
    if missing:
        raise SystemExit(
            f"fakehost: {conftest} no longer defines {', '.join(missing)}; "
            "the fixtures were renamed and this script has to follow"
        )
    return found


def _write_binaries(root: Path, conftest: Path) -> None:
    (root / "bin").mkdir(parents=True, exist_ok=True)
    sources = _sources(conftest)
    for constant, name in BINARIES.items():
        target = root / "bin" / name
        target.write_text(sources[constant], encoding="utf-8")
        os.chmod(target, 0o755)


def _write_state(root: Path, force: bool) -> None:
    """Seed the mutable files, leaving what the stand already changed alone."""
    seeds = {
        root / "awg-state.json": json.dumps(AWG_STATE, indent=2) + "\n",
        root / "etc" / "xray" / "config.json": json.dumps(XRAY_CONFIG, indent=2) + "\n",
        root / "awg.log": "",
        root / "xray.log": "",
    }
    for target, body in seeds.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        if force or not target.exists():
            target.write_text(body, encoding="utf-8")
    (root / "etc" / "amneziawg").mkdir(parents=True, exist_ok=True)


def main() -> int:
    """Lay out the fake host, and say where it went."""
    parser = argparse.ArgumentParser(
        prog="fakehost",
        description="Lay out the fake awg/xray host the stand's agent manages.",
    )
    parser.add_argument("root", type=Path, help="directory to build the fake host in")
    parser.add_argument(
        "--force",
        action="store_true",
        help="rewrite the state and the xray config, discarding what the stand did",
    )
    parser.add_argument(
        "--conftest",
        type=Path,
        default=CONFTEST,
        help="where the agent's test fixtures are, when not in this checkout",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    _write_binaries(root, args.conftest)
    _write_state(root, args.force)
    print(f"fakehost: {root} is ready", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
