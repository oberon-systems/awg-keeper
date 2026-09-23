"""Traffic and sessions, sampled from the agent on every healthcheck round."""

from __future__ import annotations

import time

from conftest import INBOUND, StubAgent
from fastapi.testclient import TestClient

KEY = "a" * 43 + "="
UUID = "2f9c1e7a-4b3d-4e8f-9a61-5d0c7b2e8f14"


def _awg_profile(client: TestClient) -> int:
    answer = client.post(
        "/api/v1/profiles",
        json={"name": "laptop", "awg": {"interface_id": 1, "public_key": KEY}},
    )
    return int(answer.json()["profile"]["id"])


def _peer(stub: StubAgent, sent: int, received: int, ago: int = 10) -> None:
    # The host's rx is what the device sent, its tx what the device received.
    stub.counters[KEY] = {
        "latest_handshake": int(time.time()) - ago,
        "transfer_rx": sent,
        "transfer_tx": received,
        "endpoint": "198.51.100.7:40123",
    }


def _stats(client: TestClient, profile: int, period: str = "7d") -> dict:
    answer = client.get(f"/api/v1/profiles/{profile}/stats?period={period}")
    assert answer.status_code == 200
    return answer.json()


def test_the_first_sample_only_sets_the_baseline(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    profile = _awg_profile(signed_in)
    _peer(stub, sent=100, received=1000)
    signed_in.post("/api/v1/agents/probe")
    found = _stats(signed_in, profile)
    assert (found["rx"], found["tx"]) == (0, 0)
    assert found["online"] is True
    assert found["last_source"] == "198.51.100.7"


def test_deltas_are_counted_from_the_device_side(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    profile = _awg_profile(signed_in)
    _peer(stub, sent=100, received=1000)
    signed_in.post("/api/v1/agents/probe")
    _peer(stub, sent=150, received=6000)
    signed_in.post("/api/v1/agents/probe")

    found = _stats(signed_in, profile)
    assert (found["rx"], found["tx"]) == (5000, 50)
    assert found["session_count"] == 1
    assert found["sessions"][0]["traffic"] == 5050
    assert found["sessions"][0]["ended_at"] is None
    assert len(found["buckets"]) == 7
    assert sum(bucket["rx"] for bucket in found["buckets"]) == 5000
    assert found["protocols"] == [
        {
            "protocol": "awg",
            "key": "awg-mgmt \u00b7 10.8.0.2/32",
            "rx": 5000,
            "tx": 50,
            "last_seen_at": found["protocols"][0]["last_seen_at"],
        }
    ]
    assert len(_stats(signed_in, profile, "24h")["buckets"]) == 24


def test_a_reset_counter_counts_from_zero(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    profile = _awg_profile(signed_in)
    _peer(stub, sent=0, received=9000)
    signed_in.post("/api/v1/agents/probe")
    _peer(stub, sent=0, received=300)
    signed_in.post("/api/v1/agents/probe")
    assert _stats(signed_in, profile)["rx"] == 300


def test_a_stale_handshake_ends_the_session(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    profile = _awg_profile(signed_in)
    _peer(stub, sent=0, received=0)
    signed_in.post("/api/v1/agents/probe")
    _peer(stub, sent=0, received=0, ago=600)
    signed_in.post("/api/v1/agents/probe")

    found = _stats(signed_in, profile)
    assert found["online"] is False
    assert found["sessions"][0]["ended_at"] is not None


def test_xray_traffic_is_sampled_too(signed_in: TestClient, stub: StubAgent) -> None:
    stub.inbounds = [dict(INBOUND)]
    signed_in.post("/api/v1/agents/probe")
    signed_in.patch(
        "/api/v1/inbounds/1", json={"enabled": True, "endpoint_host": "vpn.example"}
    )
    created = signed_in.post(
        "/api/v1/profiles",
        json={"name": "phone", "xray": {"inbound_id": 1, "id": UUID}},
    ).json()
    profile = created["profile"]["id"]

    stub.xray_counts["phone"] = {"uplink": 10, "downlink": 100, "online_ips": []}
    signed_in.post("/api/v1/agents/probe")
    stub.xray_counts["phone"] = {
        "uplink": 30,
        "downlink": 900,
        "online_ips": ["203.0.113.9"],
    }
    signed_in.post("/api/v1/agents/probe")

    found = _stats(signed_in, profile)
    assert (found["rx"], found["tx"]) == (800, 20)
    assert found["online"] is True
    assert found["sessions"][0]["protocol"] == "xray"
    assert found["sessions"][0]["source"] == "203.0.113.9"
    assert found["protocols"][0]["key"] == "reality-443"


def test_deleting_a_profile_forgets_its_stats(
    signed_in: TestClient,
    stub: StubAgent,
) -> None:
    profile = _awg_profile(signed_in)
    _peer(stub, sent=0, received=0)
    signed_in.post("/api/v1/agents/probe")
    assert signed_in.delete(f"/api/v1/profiles/{profile}").status_code == 204
    assert signed_in.get(f"/api/v1/profiles/{profile}/stats").status_code == 404


def test_an_unknown_period_is_422(signed_in: TestClient) -> None:
    profile = _awg_profile(signed_in)
    answer = signed_in.get(f"/api/v1/profiles/{profile}/stats?period=1y")
    assert answer.status_code == 422
