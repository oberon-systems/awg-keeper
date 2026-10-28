"""Snapshots of the database: on every start, on a schedule, before a change.

The database is the only copy of the obfuscation, the peers and the profiles.
Run as a module, this is the step the container takes before the migrations,
and a snapshot that fails there keeps the panel from starting.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from pydantic import ValidationError
from sqlmodel import Session

from awg_panel import logs
from awg_panel.config import Settings
from awg_panel.models import BackupSchedule
from awg_panel.schemas import BackupRead, BackupScheduleRead, BackupScheduleUpdate

LOG = logging.getLogger(__name__)

DEFAULT_CRON = "0 3 * * *"
DEFAULT_KEEP = 30
JOB = "backup"
STAMP = "%Y%m%dT%H%M%S.%fZ"
NAME = re.compile(
    r"^panel-(?P<kind>[a-z]+)-(?P<revision>[0-9A-Za-z_]+)-(?P<stamp>[0-9T.]+Z)\.sqlite$"
)


class BackupFailed(RuntimeError):
    """The snapshot could not be written, so what it guards does not run."""


def backup_dir(database: Path) -> Path:
    """Where the snapshots go: next to the database, on the same volume."""
    return database.parent / "backups"


def trigger_of(cron: str) -> CronTrigger:
    """Build the UTC trigger of a five-field crontab line; ValueError if it is not."""
    return CronTrigger.from_crontab(cron, timezone=UTC)


def _scalar(database: Path, query: str) -> object | None:
    try:
        with closing(sqlite3.connect(f"file:{database}?mode=ro", uri=True)) as db:
            row = db.execute(query).fetchone()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def snapshot(database: Path, kind: str, keep: int | None = None) -> BackupRead | None:
    """Copy the database aside with the backup API, consistent under WAL."""
    if not database.exists():
        return None
    if keep is None:
        stored = _scalar(database, "SELECT keep FROM backup_schedule LIMIT 1")
        keep = stored if isinstance(stored, int) else DEFAULT_KEEP
    revision = _scalar(database, "SELECT version_num FROM alembic_version") or "none"
    directory = backup_dir(database)
    target = directory / f"panel-{kind}-{revision}-{datetime.now(UTC):{STAMP}}.sqlite"
    partial = target.with_suffix(".tmp")
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        partial.touch(mode=0o600)
        with (
            closing(sqlite3.connect(database)) as live,
            closing(sqlite3.connect(partial)) as copy,
        ):
            live.backup(copy)
        partial.replace(target)
    except (sqlite3.Error, OSError) as exc:
        partial.unlink(missing_ok=True)
        raise BackupFailed(f"could not back up {database.name}: {exc}") from exc
    _prune(directory, kind, keep)
    LOG.info("database backed up to %s", target.name)
    return _read(target)


def _read(path: Path) -> BackupRead | None:
    match = NAME.match(path.name)
    if match is None:
        return None
    return BackupRead(
        name=path.name,
        kind=match["kind"],
        revision=match["revision"],
        size=path.stat().st_size,
        taken_at=datetime.strptime(match["stamp"], STAMP).replace(tzinfo=UTC),
    )


def _listed(directory: Path) -> list[BackupRead]:
    found = (_read(path) for path in directory.glob("panel-*.sqlite"))
    return sorted(
        (item for item in found if item is not None),
        key=lambda item: item.taken_at,
        reverse=True,
    )


def list_backups(database: Path) -> list[BackupRead]:
    """Every snapshot on disk, the newest first."""
    return _listed(backup_dir(database))


def _prune(directory: Path, kind: str, keep: int) -> None:
    taken = [item for item in _listed(directory) if item.kind == kind]
    for stale in taken[keep:]:
        (directory / stale.name).unlink(missing_ok=True)


def schedule_of(session: Session) -> BackupSchedule:
    """Return the stored schedule, or the default one until somebody saves it."""
    row = session.get(BackupSchedule, 1)
    return row or BackupSchedule(id=1, cron=DEFAULT_CRON, keep=DEFAULT_KEEP)


def next_runs(cron: str, count: int = 3) -> list[datetime]:
    """Count the next times the schedule fires, the way the scheduler does."""
    trigger = trigger_of(cron)
    runs: list[datetime] = []
    previous = None
    moment = datetime.now(UTC)
    for _ in range(count):
        fire = trigger.get_next_fire_time(previous, moment)
        if fire is None:
            break
        runs.append(fire)
        previous, moment = fire, fire
    return runs


def read_schedule(session: Session) -> BackupScheduleRead:
    """Read the schedule as the modal shows it, with its next runs."""
    row = schedule_of(session)
    return BackupScheduleRead(
        cron=row.cron,
        enabled=row.enabled,
        keep=row.keep,
        next_runs=next_runs(row.cron) if row.enabled else [],
        updated_at=row.updated_at,
        author=row.author,
    )


def save_schedule(
    session: Session,
    scheduler: BaseScheduler | None,
    body: BackupScheduleUpdate,
    author: str,
) -> BackupScheduleRead:
    """Store the schedule and hand it to the running scheduler."""
    row = schedule_of(session)
    row.cron, row.enabled, row.keep = body.cron, body.enabled, body.keep
    row.updated_at, row.author = datetime.now(UTC), author
    session.add(row)
    session.commit()
    if scheduler is not None:
        apply(scheduler, row)
    LOG.warning(
        "backup schedule set by %s: %s, %s, keep %d",
        author,
        row.cron,
        "on" if row.enabled else "off",
        row.keep,
    )
    return read_schedule(session)


def apply(scheduler: BaseScheduler, row: BackupSchedule) -> None:
    """Make the scheduler's one job follow the stored schedule."""
    scheduler.reschedule_job(JOB, trigger=trigger_of(row.cron))
    if row.enabled:
        scheduler.resume_job(JOB)
    else:
        scheduler.pause_job(JOB)


def scheduled(database: Path) -> None:
    """Take the scheduled snapshot; a failure is logged and the next run retries."""
    try:
        snapshot(database, "scheduled")
    except BackupFailed as exc:
        LOG.error("scheduled backup failed: %s", exc)


def before_change(settings: Settings, session: Session) -> None:
    """Snapshot ahead of a change that loses what it replaces."""
    snapshot(settings.database_path, "change", schedule_of(session).keep)


def main() -> int:
    """Snapshot before the migrations; non-zero keeps the container from starting."""
    try:
        settings = Settings()
    except ValidationError as exc:
        print(f"awg-keeper panel: bad configuration\n{exc}", file=sys.stderr)
        return 2
    logs.configure(settings.log_level)
    try:
        snapshot(settings.database_path, "start")
    except BackupFailed as exc:
        LOG.critical("%s; not starting without a backup", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
