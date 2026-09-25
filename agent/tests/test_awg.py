"""The awg command layer, asserted at the argv the fake binary was handed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import KEY_A, KEY_B, OBFUSCATION, SERVER_KEY, argv_log

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


def test_show_reads_the_fwmark_past_the_obfuscation(
    settings: Settings, host: Path
) -> None:
    path = host / "awg-state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state["awg0"]["fwmark"] = "0xca6c"
    path.write_text(json.dumps(state), encoding="utf-8")
    assert awg.show(settings, "awg0").fwmark == "0xca6c"


def test_probe_reads_obfuscation_in_one_show(settings: Settings, host: Path) -> None:
    found, error = awg.probe(settings)
    assert error is None
    assert found[0].obfuscation == OBFUSCATION
    assert ["show", "awg0"] in argv_log(host)
    assert not [line for line in argv_log(host) if line[2:] == ["i1"]]


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


def test_an_unreachable_conf_dir_does_not_fail_the_apply(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied(self: Path) -> bool:
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(Path, "is_dir", denied)
    peer = awg.add_peer(settings, "awg0", KEY_B, ["10.8.0.5"])
    assert peer.public_key == KEY_B
    assert awg.persist(settings, "awg0") is None


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


HEADER_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
V31 = {
    "s1": "40",
    "s2": "120",
    "s3": "24",
    "s4": "16",
    "h1": "100000-199999",
    "h2": "200000-299999",
    "h3": "300000-399999",
    "h4": "400000",
    "header-protection-key": HEADER_KEY,
    "content-padding-addition": "2-10",
    "random-trailers": "on",
}


def test_probe_reads_the_31_fields_but_never_the_key(
    settings: Settings, host: Path
) -> None:
    awg.set_obfuscation(settings, "awg0", V31)
    found, _ = awg.probe(settings)
    assert found[0].obfuscation["content-padding-addition"] == "2-10"
    assert found[0].obfuscation["random-trailers"] == "on"
    assert "header-protection-key" not in found[0].obfuscation
    assert "disable-cookies" not in found[0].obfuscation


def test_obfuscation_carries_the_key(settings: Settings) -> None:
    awg.set_obfuscation(settings, "awg0", V31)
    found = awg.obfuscation(settings, "awg0")
    assert found["header-protection-key"] == HEADER_KEY
    assert found["h1"] == "100000-199999"
    assert found["jc"] == OBFUSCATION["jc"]


def test_the_key_goes_through_stdin_never_argv(settings: Settings, host: Path) -> None:
    awg.set_obfuscation(settings, "awg0", V31)
    sets = [line for line in argv_log(host) if line[:1] == ["set"]]
    assert len(sets) == 1
    assert sets[0][-2:] == ["header-protection-key", "/dev/stdin"]
    assert HEADER_KEY not in "\t".join(sets[0])


def test_an_unchanged_set_touches_nothing(settings: Settings, host: Path) -> None:
    awg.set_obfuscation(settings, "awg0", {"jc": OBFUSCATION["jc"]})
    assert not [line for line in argv_log(host) if line[:1] == ["set"]]


@pytest.mark.parametrize(
    "broken",
    [
        {**V31, "h2": "150000-250000"},
        {**V31, "s4": "11"},
        {**V31, "random-trailers": "yes"},
        {**V31, "i1": "<b 0xc0ff><c>"},
        {**V31, "rekey-timeout": "9-3"},
        {"h1": "100000"},
        {"itime": "60"},
    ],
)
def test_a_set_awg_would_refuse_is_refused_before_it(
    settings: Settings, host: Path, broken: dict[str, str]
) -> None:
    with pytest.raises(ValueError):
        awg.set_obfuscation(settings, "awg0", broken)
    assert not [line for line in argv_log(host) if line[:1] == ["set"]]


def test_persist_moves_only_the_obfuscation_lines(settings: Settings) -> None:
    target = settings.awg_conf_dir / "awg0.conf"
    target.write_text(
        "[Interface]\n"
        "Address = 10.8.0.1/24\n"
        "ListenPort = 51820\n"
        "PrivateKey = kept\n"
        "MTU = 1280\n"
        "Jc = 3\n"
        "S1 = 99\n"
        "\n"
        "[Peer]\n"
        f"PublicKey = {KEY_A}\n"
        "AllowedIPs = 10.8.0.2/32\n",
        encoding="utf-8",
    )
    awg.set_obfuscation(settings, "awg0", V31)
    written = target.read_text(encoding="utf-8")
    for line in ("Address = 10.8.0.1/24", "PrivateKey = kept", "MTU = 1280"):
        assert f"{line}\n" in written
    assert f"Jc = {OBFUSCATION['jc']}\n" in written
    assert "S1 = 40\n" in written and "S1 = 99" not in written
    assert f"HeaderProtectionKey = {HEADER_KEY}\n" in written
    assert "ContentPaddingAddition = 2-10\n" in written
    assert written.count("[Peer]") == 1
