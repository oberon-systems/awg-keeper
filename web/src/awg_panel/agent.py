"""The client to the agents. The panel decides, the agents execute.

Synchronous on purpose: the handlers are plain `def` and run on a threadpool
worker, so an async client here would buy nothing and cost a second style.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from awg_panel.config import Settings
from awg_panel.logs import HEADER, REQUEST_ID
from awg_panel.models import Node

LOG = logging.getLogger(__name__)


class AgentError(RuntimeError):
    """The agent refused, failed, or could not be reached at all."""

    def __init__(self, reason: str, status: int | None = None) -> None:
        """Keep the status apart, so a 404 from the agent is not a 502 here."""
        super().__init__(reason)
        self.reason = reason
        self.status = status


def _detail(answer: httpx.Response) -> str:
    try:
        body = answer.json()
    except ValueError:
        return answer.reason_phrase
    detail = body.get("detail") if isinstance(body, dict) else None
    return str(detail) if detail else answer.reason_phrase


def _call(
    settings: Settings,
    node: Node,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    quiet: bool = False,
) -> dict[str, Any] | None:
    # A healthcheck logs its outcome on a change of state instead, in service.
    failed = logging.DEBUG if quiet else logging.ERROR
    if not settings.agent_token:
        LOG.error("no agent token; %s %s to %s refused", method, path, node.name)
        raise AgentError("no agent token is configured")

    headers = {
        "Authorization": f"Bearer {settings.agent_token}",
        # The same id the panel logged this request under, so one call can be
        # followed across both services.
        HEADER: REQUEST_ID.get(),
    }
    url = f"{node.endpoint.rstrip('/')}{path}"
    started = time.monotonic()
    try:
        answer = httpx.request(
            method,
            url,
            json=payload,
            headers=headers,
            timeout=settings.agent_timeout,
        )
    except httpx.HTTPError as exc:
        LOG.log(failed, "agent %s at %s unreachable: %r", node.name, node.endpoint, exc)
        raise AgentError(f"{node.name} is unreachable: {exc!r}") from exc

    elapsed = (time.monotonic() - started) * 1000
    LOG.log(
        logging.DEBUG if quiet else logging.INFO,
        "agent %s %s %s %d %.1fms",
        node.name,
        method,
        path,
        answer.status_code,
        elapsed,
    )

    if answer.status_code >= 400:
        detail = _detail(answer)
        LOG.log(
            failed,
            "agent %s %s %s answered %d: %s",
            node.name,
            method,
            path,
            answer.status_code,
            detail,
        )
        raise AgentError(
            f"{node.name} answered {answer.status_code}: {detail}", answer.status_code
        )

    if answer.status_code == 204 or not answer.content:
        return None
    try:
        parsed = answer.json()
    except ValueError as exc:
        LOG.log(failed, "agent %s %s %s answered with no json", node.name, method, path)
        raise AgentError(f"{node.name} answered with no json") from exc
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def state(settings: Settings, node: Node) -> dict[str, Any]:
    """Actual state on the node, for the drift view."""
    return _call(settings, node, "GET", "/v1/state") or {}


def status(settings: Settings, node: Node) -> dict[str, Any]:
    """Health of the node, and what awg shows for its interfaces."""
    return _call(settings, node, "GET", "/v1/status", quiet=True) or {}


def add_peer(
    settings: Settings,
    node: Node,
    interface: str,
    public_key: str,
    allowed_ips: list[str],
    keepalive: int | None = None,
) -> dict[str, Any]:
    """Push one peer to the node."""
    payload: dict[str, Any] = {
        "public_key": public_key,
        "allowed_ips": allowed_ips,
        "persistent_keepalive": keepalive,
    }
    return _call(settings, node, "POST", f"/v1/awg/{interface}/peers", payload) or {}


def remove_peer(
    settings: Settings,
    node: Node,
    interface: str,
    public_key: str,
) -> None:
    """Remove one peer from the node. An absent peer is not an error here."""
    try:
        _call(settings, node, "DELETE", f"/v1/awg/{interface}/peers/{public_key}")
    except AgentError as exc:
        # The peer is gone either way, which is what the caller wanted.
        if exc.status != 404:
            raise
