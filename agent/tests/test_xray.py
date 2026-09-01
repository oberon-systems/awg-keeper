"""The xray command layer: the api call and config.json, always together."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import UUID_A, UUID_B, argv_log

from awg_agent import xray
from awg_agent.config import Settings


def test_inbounds_are_read_from_the_config(settings: Settings) -> None:
    found = xray.inbounds(settings)
    assert [inbound.tag for inbound in found] == ["vless-in"]
    assert found[0].users[0].id == UUID_A


def test_add_user_calls_adu_and_writes_the_config(
    settings: Settings,
    host: Path,
) -> None:
    user = xray.add_user(
        settings,
        "vless-in",
        UUID_B,
        "two@node",
        flow="xtls-rprx-vision",
    )
    assert user.email == "two@node"

    called = argv_log(host, "xray")[-1]
    assert called[:3] == ["api", "adu", "--server=127.0.0.1:10085"]

    # The payload is a config fragment: adu reads whole inbound objects.
    payload = json.loads((host / "adu.json").read_text(encoding="utf-8"))
    inbound = payload["inbounds"][0]
    assert inbound["tag"] == "vless-in"
    assert inbound["protocol"] == "vless"
    assert inbound["settings"]["clients"] == [
        {"id": UUID_B, "email": "two@node", "level": 0, "flow": "xtls-rprx-vision"}
    ]

    written = json.loads(settings.xray_config.read_text(encoding="utf-8"))
    emails = [
        client["email"] for client in written["inbounds"][0]["settings"]["clients"]
    ]
    assert emails == ["one@node", "two@node"]


def test_a_duplicate_user_is_refused(settings: Settings) -> None:
    with pytest.raises(xray.DuplicateUser):
        xray.add_user(settings, "vless-in", UUID_B, "one@node")


def test_an_unknown_inbound_is_refused(settings: Settings) -> None:
    with pytest.raises(xray.UnknownInbound):
        xray.add_user(settings, "absent", UUID_B, "two@node")


def test_remove_user_calls_rmu_and_writes_the_config(
    settings: Settings,
    host: Path,
) -> None:
    xray.remove_user(settings, "vless-in", "one@node")

    assert argv_log(host, "xray")[-1] == [
        "api",
        "rmu",
        "--server=127.0.0.1:10085",
        "-tag=vless-in",
        "one@node",
    ]
    written = json.loads(settings.xray_config.read_text(encoding="utf-8"))
    assert written["inbounds"][0]["settings"]["clients"] == []


def test_removing_an_absent_user_leaves_xray_alone(
    settings: Settings,
    host: Path,
) -> None:
    with pytest.raises(xray.UnknownUser):
        xray.remove_user(settings, "vless-in", "absent@node")
    assert argv_log(host, "xray") == []
