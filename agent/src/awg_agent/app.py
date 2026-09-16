"""Building the application: settings, logging, error mapping, routes."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from awg_agent import __version__, api, logs
from awg_agent.awg import DuplicatePeer
from awg_agent.commands import CommandError
from awg_agent.config import Settings
from awg_agent.xray import DuplicateUser

LOG = logging.getLogger(__name__)


def _problem(status: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail})


def _on_conflict(request: Request, exc: Exception) -> JSONResponse:
    return _problem(409, str(exc))


def _on_missing(request: Request, exc: Exception) -> JSONResponse:
    return _problem(404, str(exc))


def _on_invalid(request: Request, exc: Exception) -> JSONResponse:
    return _problem(422, str(exc))


def _on_command(request: Request, exc: Exception) -> JSONResponse:
    # The stderr of the failed command is logged by commands.run and stays out
    # of the body: it can quote a value the caller does not get to see back.
    LOG.error("command failed: %s", exc)
    return _problem(502, "the host tool failed; see the agent log")


def _on_unexpected(request: Request, exc: Exception) -> JSONResponse:
    LOG.exception("unhandled error on %s %s", request.method, request.url.path)
    return _problem(500, "internal error; see the agent log")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Assemble the application around one Settings instance."""
    settings = settings or Settings()
    logs.configure(settings.log_level)
    LOG.info(
        "agent %s on %s:%d, interfaces %s, allowed from %s, awg %s, xray %s",
        __version__,
        settings.bind,
        settings.port,
        ",".join(settings.interfaces) or "(any)",
        ",".join(str(net) for net in settings.reachable_from()),
        settings.awg_bin,
        settings.xray_bin,
    )

    app = FastAPI(
        title="awg-keeper agent",
        version=__version__,
        docs_url="/docs" if settings.docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs else None,
    )
    app.state.settings = settings
    app.middleware("http")(logs.request_id)

    # Registered narrowest first: DuplicatePeer is a ValueError, and the
    # lookup walks the exception's own class before its bases.
    app.add_exception_handler(DuplicatePeer, _on_conflict)
    app.add_exception_handler(DuplicateUser, _on_conflict)
    app.add_exception_handler(LookupError, _on_missing)
    app.add_exception_handler(ValueError, _on_invalid)
    app.add_exception_handler(CommandError, _on_command)
    app.add_exception_handler(Exception, _on_unexpected)

    app.include_router(api.public)
    app.include_router(api.private)
    return app
