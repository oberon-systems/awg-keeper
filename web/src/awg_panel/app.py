"""Building the application: settings, logging, the engine, the SPA."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine, func
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from awg_panel import __version__, api, db, logs, service
from awg_panel.agent import AgentError
from awg_panel.config import Settings
from awg_panel.models import Interface
from awg_panel.pool import PoolExhausted
from awg_panel.service import DuplicateProfile

LOG = logging.getLogger(__name__)


def _problem(status: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail})


def _on_conflict(request: Request, exc: Exception) -> JSONResponse:
    return _problem(409, str(exc))


def _on_missing(request: Request, exc: Exception) -> JSONResponse:
    return _problem(404, str(exc))


def _on_invalid(request: Request, exc: Exception) -> JSONResponse:
    return _problem(422, str(exc))


def _on_exhausted(request: Request, exc: Exception) -> JSONResponse:
    return _problem(507, f"the address pool {exc} is exhausted")


def _on_agent(request: Request, exc: Exception) -> JSONResponse:
    LOG.error("agent call failed: %s", exc)
    return _problem(502, str(exc))


def _on_unexpected(request: Request, exc: Exception) -> JSONResponse:
    LOG.exception("unhandled error on %s %s", request.method, request.url.path)
    return _problem(500, "internal error; see the panel log")


def _log_start(settings: Settings, engine: Engine) -> None:
    LOG.info(
        "panel %s, database %s, ui %s, healthcheck %s",
        __version__,
        settings.database_path,
        settings.static_dir,
        f"every {settings.probe_interval}s" if settings.probe_interval else "off",
    )
    try:
        with Session(engine) as session:
            service.register_agents(session, settings)
            enabled = session.exec(
                select(func.count())
                .select_from(Interface)
                .where(col(Interface.enabled))
            ).one()
    except SQLAlchemyError as exc:
        LOG.error("could not read the database: %s", exc)
        return

    if not enabled:
        LOG.warning("no enabled interface: profiles cannot be issued until one is")


async def _probe_loop(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    announce = True
    while True:
        await asyncio.to_thread(service.probe_all, app.state.engine, settings, announce)
        announce = False
        await asyncio.sleep(settings.probe_interval)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    task = None
    if app.state.settings.probe_interval:
        task = asyncio.create_task(_probe_loop(app))
    yield
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def _mount_spa(app: FastAPI, static: Path) -> None:
    if not static.is_dir():
        LOG.warning("no built ui at %s; serving the api only", static)
        return

    # html=True serves index.html for a directory; the catch-all below serves
    # it for a deep link the router owns, which StaticFiles would 404.
    app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        """Hand every unmatched path to the single page application."""
        candidate = static / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(static / "index.html")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Assemble the application around one Settings instance."""
    settings = settings or Settings()
    logs.configure(settings.log_level)

    app = FastAPI(
        title="awg-keeper panel",
        version=__version__,
        docs_url="/docs" if settings.docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs else None,
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.engine = db.build_engine(settings)
    _log_start(settings, app.state.engine)
    app.middleware("http")(logs.request_id)

    # Registered narrowest first: DuplicateProfile is a ValueError, and the
    # lookup walks the exception's own class before its bases.
    app.add_exception_handler(DuplicateProfile, _on_conflict)
    app.add_exception_handler(PoolExhausted, _on_exhausted)
    app.add_exception_handler(LookupError, _on_missing)
    app.add_exception_handler(ValueError, _on_invalid)
    app.add_exception_handler(AgentError, _on_agent)
    app.add_exception_handler(Exception, _on_unexpected)

    app.include_router(api.ping)
    app.include_router(api.public)
    app.include_router(api.private)
    _mount_spa(app, settings.static_dir)
    return app
