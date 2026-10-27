"""The config history of an interface: versions, preview, rollback, reroll by hash."""

from __future__ import annotations

from conftest import OBFUSCATION, USER, StubAgent
from fastapi.testclient import TestClient

KEY = "a" * 43 + "="
VERSIONS = "/api/v1/interfaces/1/config/versions"
PREVIEW = "/api/v1/interfaces/1/config/preview"


def _edit(client: TestClient, **values: object) -> int:
    answer = client.patch(
        "/api/v1/interfaces/1/obfuscation", json={"obfuscation": values}
    )
    return answer.status_code


def _issue(client: TestClient) -> None:
    client.post(
        "/api/v1/profiles",
        json={"name": "laptop", "awg": {"interface_id": 1, "public_key": KEY}},
    )


def _reroll(client: TestClient) -> bool:
    return bool(client.get("/api/v1/profiles/1").json()["peer"]["reroll"])


def test_the_config_at_start_is_version_1(signed_in: TestClient) -> None:
    versions = signed_in.get(VERSIONS).json()
    assert [(item["version"], item["source"]) for item in versions] == [(1, "baseline")]
    assert versions[0]["current"] is True
    assert versions[0]["config"]["obfuscation"] == OBFUSCATION
    assert versions[0]["config"]["dns"] == "10.8.0.1"


def test_an_edit_is_a_version_with_its_author(signed_in: TestClient) -> None:
    assert _edit(signed_in, Jc=6) == 200
    newest = signed_in.get(VERSIONS).json()[0]
    assert (newest["version"], newest["source"], newest["author"]) == (2, "edit", USER)
    assert newest["config"]["obfuscation"]["Jc"] == 6


def test_a_failed_edit_is_no_version(signed_in: TestClient, stub: StubAgent) -> None:
    stub.fail_obfuscation = True
    assert _edit(signed_in, Jc=6) == 502
    assert len(signed_in.get(VERSIONS).json()) == 1


def test_client_settings_are_versions_and_server_ones_are_not(
    signed_in: TestClient,
) -> None:
    signed_in.patch("/api/v1/interfaces/1", json={"label": "office"})
    assert len(signed_in.get(VERSIONS).json()) == 1
    signed_in.patch("/api/v1/interfaces/1", json={"dns": "1.1.1.1"})
    newest = signed_in.get(VERSIONS).json()[0]
    assert (newest["version"], newest["config"]["dns"]) == (2, "1.1.1.1")


def test_a_zero_is_sent_and_kept_as_unset(
    signed_in: TestClient, stub: StubAgent
) -> None:
    assert _edit(signed_in, S1=0) == 200
    assert stub.calls[-1] == ("set_obfuscation", "gateway", "awg-mgmt", {"s1": "0"})
    assert "S1" not in signed_in.get(VERSIONS).json()[0]["config"]["obfuscation"]


def test_a_preview_of_an_edit_counts_the_profiles_it_stales(
    signed_in: TestClient, stub: StubAgent
) -> None:
    _issue(signed_in)
    preview = signed_in.post(PREVIEW, json={"obfuscation": {"Jc": 9}}).json()
    changed = [item for item in preview["changes"] if item["changed"]]
    assert changed == [{"field": "Jc", "before": 4, "after": 9, "changed": True}]
    assert (preview["current"], preview["stale"]) == (0, 1)
    assert preview["blocked"] == []
    assert not [call for call in stub.calls if call[0] == "set_obfuscation"]


def test_a_rollback_goes_through_the_agent_and_clears_the_reroll(
    signed_in: TestClient, stub: StubAgent
) -> None:
    _issue(signed_in)
    _edit(signed_in, Jc=6)
    assert _reroll(signed_in) is True

    preview = signed_in.post(PREVIEW, json={"version": 1}).json()
    assert (preview["version"], preview["target"]) == (2, 1)
    assert (preview["current"], preview["stale"]) == (1, 0)

    answer = signed_in.post(f"{VERSIONS}/1/apply")
    assert answer.status_code == 200, answer.text
    assert stub.calls[-1] == ("set_obfuscation", "gateway", "awg-mgmt", {"jc": "4"})
    newest = signed_in.get(VERSIONS).json()[0]
    assert (newest["version"], newest["source"], newest["rolled_back_from"]) == (
        3,
        "rollback",
        1,
    )
    assert newest["config"] == signed_in.get(VERSIONS).json()[2]["config"]
    assert _reroll(signed_in) is False


def test_a_failed_rollback_changes_nothing(
    signed_in: TestClient, stub: StubAgent
) -> None:
    _edit(signed_in, Jc=6)
    stub.fail_obfuscation = True
    assert signed_in.post(f"{VERSIONS}/1/apply").status_code == 502
    assert [item["version"] for item in signed_in.get(VERSIONS).json()] == [2, 1]


def test_what_awg_cannot_unset_blocks_the_rollback(signed_in: TestClient) -> None:
    _edit(signed_in, I1="<b 0x01>")
    preview = signed_in.post(PREVIEW, json={"version": 1}).json()
    assert preview["blocked"] == ["I1"]
    refused = signed_in.post(f"{VERSIONS}/1/apply")
    assert refused.status_code == 422
    assert "awg cannot unset I1" in refused.json()["detail"]


def test_the_current_version_is_not_applied_again(signed_in: TestClient) -> None:
    assert signed_in.post(f"{VERSIONS}/1/apply").status_code == 422


def test_an_unknown_version_is_404(signed_in: TestClient) -> None:
    assert signed_in.post(f"{VERSIONS}/9/apply").status_code == 404
    assert signed_in.post(PREVIEW, json={"version": 9}).status_code == 404
