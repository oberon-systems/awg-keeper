"""Structured logs, and the request id the panel hands on to the agent."""

from __future__ import annotations

import json
import logging
import sys
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import Request, Response

HEADER = "X-Request-Id"
REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")


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
    """Send every logger through the JSON formatter, on stdout for docker."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


async def request_id(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Mint a request id for the call, and echo it back."""
    current = request.headers.get(HEADER, "").strip() or uuid.uuid4().hex
    token = REQUEST_ID.set(current)
    try:
        response = await call_next(request)
    finally:
        REQUEST_ID.reset(token)

    response.headers[HEADER] = current
    return response
