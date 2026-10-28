"""Snapshots of the database: on start, on a schedule, before a change, on demand."""

from __future__ import annotations

import sqlite3
import stat
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from awg_panel import backup
from awg_panel.config import Settings

DAILY = {"cron": "0 3 * * *", "enabled": True, "keep": 30}


def _kinds(settings: Settings) -> list[str]:
    return [item.kind for item in backup.list_backups(settings.database_path)]


def _unwritable(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(Path, "touch", refuse)


def test_a_snapshot_holds_the_rows_and_only_the_owner_reads_it(
    settings: Settings, node: None
) -> None:
    taken = backup.snapshot(settings.database_path, "manual")
    assert taken is not None
    path = backup.backup_dir(settings.database_path) / taken.name
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT name FROM node").fetchall() == [("gateway",)]
    assert taken.kind == "manual"
    assert taken.revision == "none"
    assert not list(path.parent.glob("*.tmp"))


def test_no_database_means_no_snapshot(settings: Settings) -> None:
    assert backup.snapshot(settings.database_path, "start") is None


def test_only_the_newest_are_kept_per_kind(settings: Settings, node: None) -> None:
    backup.snapshot(settings.database_path, "start", keep=2)
    for _ in range(4):
        backup.snapshot(settings.database_path, "scheduled", keep=2)
    assert sorted(_kinds(settings)) == ["scheduled", "scheduled", "start"]


def test_a_failed_snapshot_stops_the_start(
    settings: Settings, node: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backup, "Settings", lambda: settings)
    assert backup.main() == 0
    assert _kinds(settings) == ["start"]
    _unwritable(monkeypatch)
    assert backup.main() == 1


def test_the_default_schedule_is_daily(signed_in: TestClient) -> None:
    schedule = signed_in.get("/api/v1/backups/schedule").json()
    assert schedule["cron"] == "0 3 * * *"
    assert schedule["enabled"] is True
    assert schedule["keep"] == 30
    assert len(schedule["next_runs"]) == 3
    assert schedule["author"] is None


def test_a_saved_schedule_reschedules_the_job(signed_in: TestClient) -> None:
    body = {"cron": "15 3 * * 1,4", "enabled": True, "keep": 7}
    saved = signed_in.put("/api/v1/backups/schedule", json=body).json()
    assert saved["cron"] == "15 3 * * 1,4"
    assert saved["author"] == "admin"
    assert {run[11:16] for run in saved["next_runs"]} == {"03:15"}
    job = signed_in.app.state.scheduler.get_job(backup.JOB)
    assert job.next_run_time == datetime.fromisoformat(saved["next_runs"][0])


def test_a_disabled_schedule_pauses_the_job(signed_in: TestClient) -> None:
    saved = signed_in.put(
        "/api/v1/backups/schedule", json={**DAILY, "enabled": False}
    ).json()
    assert saved["next_runs"] == []
    assert signed_in.app.state.scheduler.get_job(backup.JOB).next_run_time is None


def test_a_broken_crontab_is_refused(signed_in: TestClient) -> None:
    answer = signed_in.put(
        "/api/v1/backups/schedule", json={**DAILY, "cron": "every day"}
    )
    assert answer.status_code == 422


def test_back_up_now_lists_the_snapshot(signed_in: TestClient) -> None:
    taken = signed_in.post("/api/v1/backups")
    assert taken.status_code == 201
    listed = signed_in.get("/api/v1/backups").json()
    assert [item["name"] for item in listed] == [taken.json()["name"]]
    assert listed[0]["kind"] == "manual"


def test_a_change_is_snapshotted_first(
    signed_in: TestClient, settings: Settings
) -> None:
    answer = signed_in.patch(
        "/api/v1/interfaces/1/obfuscation", json={"obfuscation": {"Jc": 6}}
    )
    assert answer.status_code == 200
    assert _kinds(settings) == ["change"]


def test_a_change_without_a_snapshot_is_refused(
    signed_in: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _unwritable(monkeypatch)
    answer = signed_in.patch(
        "/api/v1/interfaces/1/obfuscation", json={"obfuscation": {"Jc": 6}}
    )
    assert answer.status_code == 503
    assert "nothing was changed" in answer.json()["detail"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/backups"),
        ("post", "/api/v1/backups"),
        ("get", "/api/v1/backups/schedule"),
        ("put", "/api/v1/backups/schedule"),
    ],
)
def test_backups_need_a_session(client: TestClient, method: str, path: str) -> None:
    answer = client.request(method, path, json=DAILY if method == "put" else None)
    assert answer.status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", "/api/v1/backups"), ("put", "/api/v1/backups/schedule")],
)
def test_backup_writes_need_the_csrf_token(
    signed_in: TestClient, method: str, path: str
) -> None:
    del signed_in.headers["X-CSRF-Token"]
    answer = signed_in.request(method, path, json=DAILY if method == "put" else None)
    assert answer.status_code == 403
