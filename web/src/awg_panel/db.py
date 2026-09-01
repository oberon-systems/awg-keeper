"""The engine and the session. One writer, so no pooling to think about."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry
from sqlmodel import Session, create_engine

from awg_panel.config import Settings


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
    """WAL, so a reader never blocks the writer, and real foreign keys."""
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def build_engine(settings: Settings) -> Engine:
    """Open the database, creating its directory when it is not there yet."""
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        settings.database_url,
        # The session is opened per request on a threadpool worker, which is
        # not the thread the engine was built on.
        connect_args={"check_same_thread": False},
    )


def session_of(engine: Engine) -> Iterator[Session]:
    """One session per request, committed by the handler that used it."""
    with Session(engine) as session:
        yield session
