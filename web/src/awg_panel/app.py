"""Building the application: settings, logging, the engine, the SPA."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from awg_panel import __version__, api, db, logs
from awg_panel.agent import AgentError
from awg_panel.config import Settings
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
    )
    app.state.settings = settings
    app.state.engine = db.build_engine(settings)
    app.middleware("http")(logs.request_id)

    # Registered narrowest first: DuplicateProfile is a ValueError, and the
    # lookup walks the exception's own class before its bases.
    app.add_exception_handler(DuplicateProfile, _on_conflict)
    app.add_exception_handler(PoolExhausted, _on_exhausted)
    app.add_exception_handler(LookupError, _on_missing)
    app.add_exception_handler(ValueError, _on_invalid)
    app.add_exception_handler(AgentError, _on_agent)

    app.include_router(api.ping)
    app.include_router(api.public)
    app.include_router(api.private)
    _mount_spa(app, settings.static_dir)
    return app
