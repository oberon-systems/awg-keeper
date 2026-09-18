"""The awg command layer, asserted at the argv the fake binary was handed."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import KEY_A, KEY_B, SERVER_KEY, argv_log

from awg_agent import awg
from awg_agent.commands import CommandError
from awg_agent.config import Settings


def test_show_parses_the_dump(settings: Settings) -> None:
    interface = awg.show(settings, "awg0")
    assert interface.public_key == SERVER_KEY
    assert interface.listen_port == 51820
    assert [peer.public_key for peer in interface.peers] == [KEY_A]
    assert interface.peers[0].allowed_ips == ["10.8.0.2/32"]
    assert interface.peers[0].transfer_rx == 1024
    assert interface.peers[0].transfer_tx == 2048


def test_interfaces_are_narrowed_to_the_managed_ones(settings: Settings) -> None:
    assert awg.interfaces(settings) == ["awg0"]


def test_an_unmanaged_interface_is_refused(settings: Settings) -> None:
    with pytest.raises(ValueError):
        awg.show(settings, "awg9")


def test_add_peer_uses_exactly_one_set(settings: Settings, host: Path) -> None:
    peer = awg.add_peer(settings, "awg0", KEY_B, ["10.8.0.5"], keepalive=25)

    assert peer.public_key == KEY_B
    assert peer.allowed_ips == ["10.8.0.5/32"]
    assert [
        line
        for line in argv_log(host)
        if line[:1] == ["set"] or line[:1] == ["showconf"]
    ] == [
        [
            "set",
            "awg0",
            "peer",
            KEY_B,
            "allowed-ips",
            "10.8.0.5/32",
            "persistent-keepalive",
            "25",
        ],
        ["showconf", "awg0"],
    ]


def test_add_peer_persists_the_interface(settings: Settings) -> None:
    awg.add_peer(settings, "awg0", KEY_B, ["10.8.0.5"])
    written = (settings.awg_conf_dir / "awg0.conf").read_text(encoding="utf-8")
    assert "[Interface]" in written
    assert KEY_B in written


def test_persist_keeps_what_awg_quick_needs(settings: Settings) -> None:
    target = settings.awg_conf_dir / "awg0.conf"
    target.write_text(
        "[Interface]\n"
        "PrivateKey = kept\n"
        "Address = 10.8.0.1/24\n"
        "PostUp = iptables -t nat -A POSTROUTING -j MASQUERADE\n"
        "\n"
        "[Peer]\n"
        "PublicKey = stale\n"
        "AllowedIPs = 10.8.0.9/32\n",
        encoding="utf-8",
    )
    awg.add_peer(settings, "awg0", KEY_B, ["10.8.0.5"])
    written = target.read_text(encoding="utf-8")
    assert "Address = 10.8.0.1/24\n" in written
    assert "PostUp = iptables" in written
    assert "PrivateKey = kept\n" in written
    assert "stale" not in written
    assert written.count("[Peer]") == 2
    assert KEY_A in written
    assert KEY_B in written


def test_a_failed_persist_does_not_fail_the_apply(settings: Settings) -> None:
    (settings.awg_conf_dir / "awg0.conf").mkdir()
    peer = awg.add_peer(settings, "awg0", KEY_B, ["10.8.0.5"])
    assert peer.public_key == KEY_B


def test_a_duplicate_peer_is_refused(settings: Settings) -> None:
    with pytest.raises(awg.DuplicatePeer):
        awg.add_peer(settings, "awg0", KEY_A, ["10.8.0.2"])


def test_remove_peer(settings: Settings, host: Path) -> None:
    awg.remove_peer(settings, "awg0", KEY_A)
    assert awg.list_peers(settings, "awg0") == []
    assert ["set", "awg0", "peer", KEY_A, "remove"] in argv_log(host)


def test_removing_an_absent_peer_is_unknown(settings: Settings) -> None:
    with pytest.raises(awg.UnknownPeer):
        awg.remove_peer(settings, "awg0", KEY_B)


def test_a_failing_binary_becomes_a_command_error(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_AWG_FAIL", "1")
    with pytest.raises(CommandError) as caught:
        awg.show(settings, "awg0")
    assert "Operation not permitted" in caught.value.stderr
