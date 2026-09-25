"""The xray command layer: the api call and config.json, always together."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from conftest import REALITY_KEY, UUID_A, UUID_B, argv_log

from awg_agent import xray
from awg_agent.config import Settings


def test_inbounds_are_read_from_the_config(settings: Settings) -> None:
    found = xray.inbounds(settings)
    assert [inbound.tag for inbound in found] == ["vless-in"]
    assert found[0].users[0].id == UUID_A


def test_the_transport_is_read_from_the_config(settings: Settings) -> None:
    found = xray.inbounds(settings)[0]
    assert (found.protocol, found.port, found.network, found.security) == (
        "vless",
        443,
        "tcp",
        "reality",
    )
    assert found.server_names == ["www.example.com"]
    assert found.short_ids == ["0123456789abcdef"]
    assert found.public_key == REALITY_KEY[::-1]


def test_the_private_key_never_leaves_the_host(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    found = xray.inbounds(settings)[0].model_dump_json()
    reported = xray.health(settings)[0].model_dump_json()
    assert REALITY_KEY not in found
    assert REALITY_KEY not in reported
    assert REALITY_KEY not in caplog.text


def test_the_public_key_is_derived_once(settings: Settings, host: Path) -> None:
    xray.health(settings)
    xray.health(settings)
    derived = [argv for argv in argv_log(host, "xray") if argv[0] == "x25519"]
    assert len(derived) == 1


def test_a_failed_derivation_leaves_the_key_empty(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("FAKE_XRAY_FAIL", "1")
    caplog.set_level(logging.DEBUG)
    assert xray.health(settings)[0].public_key is None
    assert REALITY_KEY not in caplog.text


def test_the_health_counts_the_clients(settings: Settings) -> None:
    found = xray.health(settings)
    assert [(item.tag, item.clients) for item in found] == [("vless-in", 1)]


def test_no_config_means_no_inbounds(settings: Settings) -> None:
    settings.xray_config.unlink()
    assert xray.health(settings) == []


def test_stats_turned_off_are_not_an_error(settings: Settings) -> None:
    assert xray.stats(settings).enabled is False


def test_stats_are_counted_per_client(settings: Settings, host: Path) -> None:
    counted = {"one@node": {"uplink": 10, "downlink": 700, "ips": ["198.51.100.7"]}}
    (host / "xray-stats.json").write_text(json.dumps(counted), encoding="utf-8")
    found = xray.stats(settings)
    assert found.enabled is True
    assert [(u.email, u.uplink, u.downlink, u.online_ips) for u in found.users] == [
        ("one@node", 10, 700, ["198.51.100.7"])
    ]


def test_stats_without_the_online_map_still_count(
    settings: Settings,
    host: Path,
) -> None:
    counted = {"one@node": {"uplink": 1, "downlink": 2}}
    (host / "xray-stats.json").write_text(json.dumps(counted), encoding="utf-8")
    user = xray.stats(settings).users[0]
    assert (user.uplink, user.downlink, user.online_ips) == (1, 2, [])


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


def test_a_rename_keeps_the_id_and_moves_the_tag(
    settings: Settings, host: Path
) -> None:
    user = xray.rename_user(settings, "vless-in", "one@node", "two@node")
    assert (user.email, user.id) == ("two@node", UUID_A)
    saved = json.loads(settings.xray_config.read_text(encoding="utf-8"))
    assert saved["inbounds"][0]["settings"]["clients"][0]["email"] == "two@node"
    calls = [argv[1] for argv in argv_log(host, "xray") if argv[0] == "api"]
    assert calls == ["rmu", "adu"]
    payload = json.loads((host / "adu.json").read_text(encoding="utf-8"))
    assert payload["inbounds"][0]["settings"]["clients"][0]["id"] == UUID_A


def test_a_rename_onto_a_taken_tag_is_refused(settings: Settings) -> None:
    xray.add_user(settings, "vless-in", UUID_B, "two@node")
    with pytest.raises(xray.DuplicateUser):
        xray.rename_user(settings, "vless-in", "one@node", "two@node")


def test_a_rename_of_an_unknown_client_is_refused(settings: Settings) -> None:
    with pytest.raises(xray.UnknownUser):
        xray.rename_user(settings, "vless-in", "nobody@node", "two@node")
