"""Who may talk to the panel: a pre-set account, and a pre-set source subnet.

The session is a signed cookie rather than a row: the panel has one account, so
a server-side session table would buy nothing but a second thing to expire.
"""

from __future__ import annotations

import logging
import secrets
import time
from ipaddress import ip_address

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from awg_panel.config import Settings

LOG = logging.getLogger(__name__)

SESSION_COOKIE = "awg_session"
CSRF_COOKIE = "awg_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

_hasher = PasswordHasher()
# username -> (failures, locked until). One account and one process, so a dict
# is the whole of the lockout state.
_failures: dict[str, tuple[int, float]] = {}


def settings_of(request: Request) -> Settings:
    """Return the one Settings instance, put on the app by create_app()."""
    return request.app.state.settings


def hash_password(password: str) -> str:
    """Hash a password the way the panel expects to find it in the config."""
    return _hasher.hash(password)


def _locked(settings: Settings, user: str) -> float:
    failures, until = _failures.get(user, (0, 0.0))
    if failures >= settings.login_attempts and until > time.time():
        return until
    return 0.0


def authenticate(settings: Settings, user: str, password: str) -> None:
    """Check the credentials, or raise. Counts failures and locks out."""
    until = _locked(settings, user)
    if until:
        raise HTTPException(429, f"locked out for {int(until - time.time())}s")

    # Compared even when the user is wrong, so a bad username and a bad
    # password take the same time to answer.
    known = secrets.compare_digest(user.encode(), settings.admin_user.encode())
    try:
        _hasher.verify(settings.admin_password_hash, password)
        matched = known
    except (VerifyMismatchError, VerificationError):
        matched = False

    if not matched:
        failures, _ = _failures.get(user, (0, 0.0))
        _failures[user] = (failures + 1, time.time() + settings.lockout_seconds)
        LOG.warning("failed login for %r", user)
        raise HTTPException(401, "bad credentials")

    _failures.pop(user, None)


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="awg-panel-session")


def open_session(settings: Settings, response: Response, user: str) -> str:
    """Set the session and the CSRF cookies, and return the CSRF token."""
    token = _serializer(settings).dumps({"user": user})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/",
    )
    csrf = secrets.token_urlsafe(32)
    # Readable by the SPA on purpose: it echoes it back in a header, and an
    # attacker's origin can send the cookie but cannot read it.
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=settings.session_ttl,
        httponly=False,
        samesite="strict",
        secure=settings.cookie_secure,
        path="/",
    )
    return csrf


def close_session(response: Response) -> None:
    """Drop both cookies."""
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def require_session(request: Request) -> str:
    """Refuse anything without a valid session, and check CSRF on writes."""
    settings = settings_of(request)
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        raise HTTPException(401, "not signed in")

    try:
        payload = _serializer(settings).loads(token, max_age=settings.session_ttl)
    except SignatureExpired as exc:
        raise HTTPException(401, "session expired") from exc
    except BadSignature as exc:
        raise HTTPException(401, "bad session") from exc

    if request.method not in SAFE_METHODS:
        cookie = request.cookies.get(CSRF_COOKIE, "")
        header = request.headers.get(CSRF_HEADER, "")
        if not cookie or not secrets.compare_digest(cookie, header):
            raise HTTPException(403, "csrf token missing or wrong")

    return str(payload.get("user", ""))


def require_source(request: Request) -> None:
    """Refuse anything from outside the pre-set subnets. Empty allows all."""
    networks = settings_of(request).allowed_subnets
    if not networks:
        return

    client = request.client
    if client is None:
        raise HTTPException(403, "source address unknown")

    try:
        source = ip_address(client.host)
    except ValueError as exc:
        raise HTTPException(403, "source address unknown") from exc

    if not any(source in network for network in networks):
        LOG.warning("refused %s: outside the allowed subnets", source)
        raise HTTPException(403, "source address not allowed")
