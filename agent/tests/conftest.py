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

from awg_agent import xray
from awg_agent.app import create_app
from awg_agent.config import Settings

TOKEN = "0123456789abcdef0123456789abcdef"
SOURCE = ("127.0.0.1", 51820)

KEY_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa0="
KEY_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb1="
SERVER_KEY = "cccccccccccccccccccccccccccccccccccccccccc2="

OBFUSCATION = {"jc": "4", "jmin": "50", "jmax": "1000", "h1": "1077035230"}

UUID_A = "6f1f0b8e-0b1a-4c2e-9d3f-5a6b7c8d9e01"
UUID_B = "7a2f1c9d-1c2b-4d3f-8e4a-6b7c8d9e0f12"
REALITY_KEY = "yH8sQk2mVb7Lr4Tn1Wc9Xe5Pz3Ad6Fg0Jh2Ku8Nq4R"

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


FIELDS = (
    "jc", "jmin", "jmax", "s1", "s2", "s3", "s4",
    "h1", "h2", "h3", "h4", "i1", "i2", "i3", "i4", "i5",
    "header-protection-key", "content-padding-addition", "rekey-after-time",
    "rekey-timeout", "reject-after-time", "keepalive-timeout",
    "max-handshake-attempts", "random-trailers", "disable-cookies",
)
KEYS = {"jc": "Jc", "jmin": "Jmin", "jmax": "Jmax"}


def unset(name):
    if name in ("h1", "h2", "h3", "h4"):
        return name[1]
    if name[0] == "i" and len(name) == 2:
        return "(null)"
    if name == "header-protection-key":
        return "(none)"
    return "off" if name in ("random-trailers", "disable-cookies") else "0"


def conf_key(name):
    return KEYS.get(name) or "".join(part.title() for part in name.split("-"))


def save():
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle)


if argv[:1] == ["--version"]:
    print("amneziawg-tools v1.0.20241018")
elif argv[:2] == ["show", "interfaces"]:
    print(" ".join(state))
elif len(argv) == 3 and argv[0] == "show" and argv[2] == "peers":
    for key in state[argv[1]]["peers"]:
        print(key)
elif len(argv) == 3 and argv[0] == "show" and argv[2] == "public-key":
    print(state[argv[1]]["public_key"])
elif len(argv) == 3 and argv[0] == "show" and argv[2] == "listen-port":
    print(state[argv[1]]["listen_port"])
elif len(argv) == 2 and argv[0] == "show":
    iface = state[argv[1]]
    print("interface: %s" % argv[1])
    print("  public key: %s" % iface["public_key"])
    print("  private key: (hidden)")
    print("  listening port: %d" % iface["listen_port"])
    for name in FIELDS:
        value = iface.get("obfuscation", {}).get(name, unset(name))
        if name == "header-protection-key" and value != "(none)":
            value = "(hidden)"
        print("  %s: %s" % (name.replace("-", " "), value))
    for key, peer in iface["peers"].items():
        print("")
        print("peer: %s" % key)
        print("  allowed ips: %s" % peer["allowed_ips"])
elif len(argv) == 3 and argv[0] == "show" and argv[2] == "dump":
    iface = state[argv[1]]
    obfuscation = iface.get("obfuscation", {})
    columns = [obfuscation.get(name, unset(name)) for name in FIELDS]
    head = ["(none)", iface["public_key"], str(iface["listen_port"]), *columns]
    print("\\t".join([*head, iface.get("fwmark", "off")]))
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
    for name, value in iface.get("obfuscation", {}).items():
        print("%s = %s" % (conf_key(name), value))
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
elif argv[:1] == ["set"]:
    iface = state[argv[1]]
    rest = argv[2:]
    for name, value in zip(rest[::2], rest[1::2]):
        if name not in FIELDS:
            sys.stderr.write("Invalid argument: %s\\n" % name)
            sys.exit(1)
        if name == "header-protection-key":
            value = (sys.stdin if value == "/dev/stdin" else open(value)).read().strip()
        iface.setdefault("obfuscation", {})[name] = value
    save()
else:
    sys.stderr.write("awg: unknown command %s\\n" % argv)
    sys.exit(1)
'''

FAKE_XRAY = '''#!/usr/bin/env python3
"""A stand-in for xray: logs its argv, and the payload adu was handed."""
import json
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
elif argv[:2] in (["api", "statsquery"], ["api", "statsonlineiplist"]):
    path = os.environ.get("FAKE_XRAY_STATS", "")
    if not os.path.exists(path):
        sys.stderr.write("xray: unknown service xray.app.stats.command.StatsService\\n")
        sys.exit(1)
    with open(path, encoding="utf-8") as handle:
        counted = json.load(handle)
    if argv[1] == "statsquery":
        stat = []
        for email, item in counted.items():
            for name in ("uplink", "downlink"):
                stat.append({
                    "name": "user>>>%s>>>traffic>>>%s" % (email, name),
                    "value": str(item.get(name, 0)),
                })
        print(json.dumps({"stat": stat}))
    else:
        email = argv[argv.index("-email") + 1]
        ips = counted.get(email, {}).get("ips")
        if ips is None:
            sys.stderr.write("xray: online map not enabled\\n")
            sys.exit(1)
        print(json.dumps({"name": "user>>>%s>>>online" % email,
                          "ips": {ip: 1758553200 for ip in ips}}))
elif argv[:2] == ["x25519", "-i"]:
    # Not the real curve: reversing is enough for a key the tests can predict.
    print("PrivateKey: %s" % argv[2])
    print("Password: %s" % argv[2][::-1])
    print("Hash32: -")
else:
    sys.stderr.write("xray: unknown command %s\\n" % argv)
    sys.exit(1)
'''


FAKE_IP = '''#!/usr/bin/env python3
"""A stand-in for ip: answers `-j address show dev` out of the awg state."""
import json
import os
import sys

argv = sys.argv[1:]
with open(os.environ["FAKE_AWG_STATE"], encoding="utf-8") as handle:
    state = json.load(handle)

if argv[:4] != ["-j", "address", "show", "dev"] or argv[4] not in state:
    sys.stderr.write("Device does not exist.\\n")
    sys.exit(1)

info = []
for item in state[argv[4]].get("addresses", []):
    local, prefix = item.split("/")
    family = "inet6" if ":" in local else "inet"
    info.append(
        {"family": family, "local": local, "prefixlen": int(prefix), "scope": "global"}
    )
info.append({"family": "inet6", "local": "fe80::1", "prefixlen": 64, "scope": "link"})
print(json.dumps([{"ifname": argv[4], "addr_info": info}]))
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


@pytest.fixture(autouse=True)
def _forget_derived_keys() -> Iterator[None]:
    """Forget the derived Reality keys, so each test starts with a cold cache."""
    xray._PUBLIC_KEYS.clear()
    yield
    xray._PUBLIC_KEYS.clear()


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a fake host: the two binaries, their logs and their state."""
    root = tmp_path / "host"
    (root / "bin").mkdir(parents=True)
    (root / "etc").mkdir()

    _script(root / "bin" / "awg", FAKE_AWG)
    _script(root / "bin" / "xray", FAKE_XRAY)
    _script(root / "bin" / "ip", FAKE_IP)

    state = {
        "awg0": {
            "public_key": SERVER_KEY,
            "listen_port": 51820,
            "addresses": ["10.8.0.1/24"],
            "obfuscation": OBFUSCATION,
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
                "listen": "0.0.0.0",
                "port": 443,
                "protocol": "vless",
                "settings": {"clients": [{"id": UUID_A, "email": "one@node"}]},
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "privateKey": REALITY_KEY,
                        "serverNames": ["www.example.com"],
                        "shortIds": ["", "0123456789abcdef"],
                    },
                },
            }
        ]
    }
    (root / "etc" / "config.json").write_text(json.dumps(config), encoding="utf-8")

    monkeypatch.setenv("FAKE_AWG_LOG", str(root / "awg.log"))
    monkeypatch.setenv("FAKE_AWG_STATE", str(root / "awg-state.json"))
    monkeypatch.setenv("FAKE_XRAY_LOG", str(root / "xray.log"))
    monkeypatch.setenv("FAKE_XRAY_PAYLOAD", str(root / "adu.json"))
    monkeypatch.setenv("FAKE_XRAY_STATS", str(root / "xray-stats.json"))
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
        ip_bin=str(host / "bin" / "ip"),
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
