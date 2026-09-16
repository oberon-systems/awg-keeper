"""Structured logs, and the request id the Panel propagates into them."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import Request, Response

HEADER = "X-Request-Id"
REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")
ACCESS = logging.getLogger("awg_agent.access")


class JsonFormatter(logging.Formatter):
    """One JSON object per line, so a log shipper needs no regular expression."""

    def format(self, record: logging.LogRecord) -> str:
        """Render the record, carrying the request id of the call it came from."""
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": REQUEST_ID.get(),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure(level: str) -> None:
    """Send every logger through the JSON formatter, on stdout for journald."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    # Replaces only an earlier JSON handler, so a test's capturing handler survives.
    kept = [h for h in root.handlers if not isinstance(h.formatter, JsonFormatter)]
    root.handlers = [*kept, handler]
    root.setLevel(level)


async def request_id(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Adopt the Panel's request id, or mint one, echo it back, log the call."""
    current = request.headers.get(HEADER, "").strip() or uuid.uuid4().hex
    token = REQUEST_ID.set(current)
    started = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
    finally:
        ACCESS.info(
            "%s %s %d %.1fms from %s",
            request.method,
            request.url.path,
            status,
            (time.monotonic() - started) * 1000,
            request.client.host if request.client else "-",
        )
        REQUEST_ID.reset(token)

    response.headers[HEADER] = current
    return response
