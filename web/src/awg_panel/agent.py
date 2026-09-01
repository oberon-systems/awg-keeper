"""The client to the agent. The panel decides, the agent executes.

Synchronous on purpose: the handlers are plain `def` and run on a threadpool
worker, so an async client here would buy nothing and cost a second style.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from awg_panel.config import Settings
from awg_panel.logs import HEADER, REQUEST_ID

LOG = logging.getLogger(__name__)


class AgentError(RuntimeError):
    """The agent refused, failed, or could not be reached at all."""

    def __init__(self, reason: str, status: int | None = None) -> None:
        """Keep the status apart, so a 404 from the agent is not a 502 here."""
        super().__init__(reason)
        self.reason = reason
        self.status = status


def _call(
    settings: Settings,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not settings.agent_token:
        raise AgentError("no agent token is configured")

    headers = {
        "Authorization": f"Bearer {settings.agent_token}",
        # The same id the panel logged this request under, so one call can be
        # followed across both services.
        HEADER: REQUEST_ID.get(),
    }
    url = f"{settings.agent_url.rstrip('/')}{path}"
    try:
        answer = httpx.request(
            method,
            url,
            json=payload,
            headers=headers,
            timeout=settings.agent_timeout,
        )
    except httpx.HTTPError as exc:
        LOG.error("agent unreachable: %s", exc)
        raise AgentError("the agent is unreachable") from exc

    if answer.status_code >= 400:
        LOG.error("agent %s %s answered %d", method, path, answer.status_code)
        raise AgentError("the agent refused the change", answer.status_code)

    if answer.status_code == 204 or not answer.content:
        return None
    parsed = answer.json()
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def state(settings: Settings) -> dict[str, Any]:
    """Actual state on the node, for the drift view."""
    return _call(settings, "GET", "/v1/state") or {}


def health(settings: Settings) -> dict[str, Any]:
    """Liveness of the node, and the versions it runs."""
    return _call(settings, "GET", "/v1/health") or {}


def add_peer(
    settings: Settings,
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
    return _call(settings, "POST", f"/v1/awg/{interface}/peers", payload) or {}


def remove_peer(settings: Settings, interface: str, public_key: str) -> None:
    """Remove one peer from the node. An absent peer is not an error here."""
    try:
        _call(settings, "DELETE", f"/v1/awg/{interface}/peers/{public_key}")
    except AgentError as exc:
        # The peer is gone either way, which is what the caller wanted.
        if exc.status != 404:
            raise
