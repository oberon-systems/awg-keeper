"""Fixtures: fake awg and xray binaries, and a client wired to them.

Nothing in the suite touches a real interface, a real Xray or root. Each fake
appends its argv to a log the tests assert against, and keeps enough state for
a write to be visible to the next read.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from awg_agent.app import create_app
from awg_agent.config import Settings

TOKEN = "0123456789abcdef0123456789abcdef"
SOURCE = ("127.0.0.1", 51820)

KEY_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa0="
KEY_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb1="
SERVER_KEY = "cccccccccccccccccccccccccccccccccccccccccc2="

UUID_A = "6f1f0b8e-0b1a-4c2e-9d3f-5a6b7c8d9e01"
UUID_B = "7a2f1c9d-1c2b-4d3f-8e4a-6b7c8d9e0f12"

FAKE_AWG = '''#!/usr/bin/env python3
"""A stand-in for awg: logs its argv, and remembers what was set."""
import json
import os
import sys

argv = sys.argv[1:]
with open(os.environ["FAKE_AWG_LOG"], "a", encoding="utf-8") as handle:
    handle.write("\\t".join(argv) + "\\n")

path = os.environ["FAKE_AWG_STATE"]
with open(path, encoding="utf-8") as handle:
    state = json.load(handle)

if os.environ.get("FAKE_AWG_FAIL"):
    sys.stderr.write("awg: RTNETLINK answers: Operation not permitted\\n")
    sys.exit(1)


def save():
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle)


if argv[:1] == ["--version"]:
    print("amneziawg-tools v1.0.20241018")
elif argv[:2] == ["show", "interfaces"]:
    print(" ".join(state))
elif len(argv) == 3 and argv[0] == "show" and argv[2] == "dump":
    iface = state[argv[1]]
    print("\\t".join(["(none)", iface["public_key"], str(iface["listen_port"]), "off"]))
    for key, peer in iface["peers"].items():
        print("\\t".join([
            key,
            "(none)",
            peer.get("endpoint", "(none)"),
            peer["allowed_ips"],
            str(peer.get("handshake", 0)),
            str(peer.get("rx", 0)),
            str(peer.get("tx", 0)),
            str(peer.get("keepalive", "off")),
        ]))
elif argv[:1] == ["showconf"]:
    iface = state[argv[1]]
    print("[Interface]")
    print("ListenPort = %d" % iface["listen_port"])
    for key, peer in iface["peers"].items():
        print("")
        print("[Peer]")
        print("PublicKey = %s" % key)
        print("AllowedIPs = %s" % peer["allowed_ips"])
elif argv[:1] == ["set"] and argv[2] == "peer":
    iface = state[argv[1]]
    key = argv[3]
    if argv[4:5] == ["remove"]:
        iface["peers"].pop(key, None)
    else:
        peer = iface["peers"].setdefault(key, {"allowed_ips": ""})
        rest = argv[4:]
        for name, value in zip(rest[::2], rest[1::2]):
            if name == "allowed-ips":
                peer["allowed_ips"] = value
            elif name == "persistent-keepalive":
                peer["keepalive"] = int(value)
    save()
else:
    sys.stderr.write("awg: unknown command %s\\n" % argv)
    sys.exit(1)
'''

FAKE_XRAY = '''#!/usr/bin/env python3
"""A stand-in for xray: logs its argv, and the payload adu was handed."""
import os
import sys

argv = sys.argv[1:]
with open(os.environ["FAKE_XRAY_LOG"], "a", encoding="utf-8") as handle:
    handle.write("\\t".join(argv) + "\\n")

if os.environ.get("FAKE_XRAY_FAIL"):
    sys.stderr.write("xray: failed to dial 127.0.0.1:10085\\n")
    sys.exit(1)

if argv[:1] == ["version"]:
    print("Xray 1.8.24 (Xray, Penetrates Everything.)")
elif argv[:2] == ["api", "adu"]:
    with open(argv[-1], encoding="utf-8") as handle:
        payload = handle.read()
    with open(os.environ["FAKE_XRAY_PAYLOAD"], "w", encoding="utf-8") as handle:
        handle.write(payload)
elif argv[:2] == ["api", "rmu"]:
    pass
else:
    sys.stderr.write("xray: unknown command %s\\n" % argv)
    sys.exit(1)
'''


def _script(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a developer's own AWG_KEEPER_* out of the suite."""
    for name in list(os.environ):
        if name.startswith("AWG_KEEPER_"):
            monkeypatch.delenv(name)


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a fake host: the two binaries, their logs and their state."""
    root = tmp_path / "host"
    (root / "bin").mkdir(parents=True)
    (root / "etc").mkdir()

    _script(root / "bin" / "awg", FAKE_AWG)
    _script(root / "bin" / "xray", FAKE_XRAY)

    state = {
        "awg0": {
            "public_key": SERVER_KEY,
            "listen_port": 51820,
            "peers": {KEY_A: {"allowed_ips": "10.8.0.2/32", "rx": 1024, "tx": 2048}},
        }
    }
    (root / "awg-state.json").write_text(json.dumps(state), encoding="utf-8")
    (root / "awg.log").write_text("", encoding="utf-8")
    (root / "xray.log").write_text("", encoding="utf-8")

    config = {
        "inbounds": [
            {
                "tag": "vless-in",
                "protocol": "vless",
                "settings": {"clients": [{"id": UUID_A, "email": "one@node"}]},
            }
        ]
    }
    (root / "etc" / "config.json").write_text(json.dumps(config), encoding="utf-8")

    monkeypatch.setenv("FAKE_AWG_LOG", str(root / "awg.log"))
    monkeypatch.setenv("FAKE_AWG_STATE", str(root / "awg-state.json"))
    monkeypatch.setenv("FAKE_XRAY_LOG", str(root / "xray.log"))
    monkeypatch.setenv("FAKE_XRAY_PAYLOAD", str(root / "adu.json"))
    return root


@pytest.fixture
def settings(host: Path, tmp_path: Path) -> Settings:
    """Build settings pointing at the fake host rather than the real one."""
    conf_dir = tmp_path / "amneziawg"
    conf_dir.mkdir()
    return Settings(
        token=TOKEN,
        allowed_subnets="127.0.0.0/8",
        interfaces="awg0",
        awg_bin=str(host / "bin" / "awg"),
        awg_conf_dir=conf_dir,
        xray_bin=str(host / "bin" / "xray"),
        xray_config=host / "etc" / "config.json",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """Build a client that authenticates, from an address the settings allow."""
    with TestClient(create_app(settings), client=SOURCE) as test_client:
        test_client.headers.update({"Authorization": f"Bearer {TOKEN}"})
        yield test_client


def argv_log(host: Path, name: str = "awg") -> list[list[str]]:
    """Every command the fake binary was called with, in order."""
    text = (host / f"{name}.log").read_text(encoding="utf-8")
    return [line.split("\t") for line in text.splitlines() if line]
