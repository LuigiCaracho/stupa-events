"""Session and token handling.

The principal session (OIDC) is a server-side row. The browser holds only a signed,
opaque `sid` in an HttpOnly cookie. Nobody can forge a token from `SESSION_SECRET`
alone, because a matching row must exist. The server can end a session at any time.

The OIDC transaction is a short-lived signed cookie with `state`, `code_verifier` and
`nonce` for the auth-code plus PKCE flow. It is stateless and needs no server store.

A bad signature or an expiry gives `None`, never an exception to the outside. The caller
maps `None` to 401.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/auth/sessions.py (no applicant, no OAuth)
"""

from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlsplit

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import (
    MAX_SESSION_DAYS,
    SESSION_CLIENT_WEB,
    SESSION_CLIENTS,
    AuthSession,
)

_OIDC_TX_SALT = "oidc-tx"
_SID_SALT = "principal-sid"
_SID_BYTES = 32


def _serializer(secret: str, salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt=salt)


# OIDC transaction cookie: state, PKCE verifier, nonce and the session client.
def issue_oidc_tx(
    secret: str,
    state: str,
    verifier: str,
    nonce: str,
    client: str = SESSION_CLIENT_WEB,
    return_to: str | None = None,
) -> str:
    data = {"state": state, "verifier": verifier, "nonce": nonce, "client": client}
    if return_to:
        data["return_to"] = return_to
    return _serializer(secret, _OIDC_TX_SALT).dumps(data)


_RETURN_TO_MAX = 1024


def safe_return_to(value: str | None) -> str | None:
    """Return `value` if it is a path of this app to land on after the login, else `None`.

    Only a same-origin path is accepted: it starts with exactly one `/` (so it has no
    scheme and no host), has no backslash (which a browser reads as `/`), no whitespace
    or control character, and is not under `/api/`. A dot segment or an encoded dot,
    slash or backslash is refused too, because the browser resolves it and could reach
    `/api/` that way. This keeps the redirect after the callback from becoming an open
    redirect.
    """
    if not value or len(value) > _RETURN_TO_MAX:
        return None
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return None
    if any(c.isspace() or not c.isprintable() for c in value):
        return None
    path = urlsplit(value).path
    lowered = path.lower()
    if any(code in lowered for code in ("%2e", "%2f", "%5c")):
        return None
    if any(segment in {".", ".."} for segment in path.split("/")):
        return None
    if path == "/api" or path.startswith("/api/"):
        return None
    return value


def load_oidc_tx(secret: str, value: str, max_age: int) -> dict[str, str] | None:
    """Return the transaction, or `None` for a bad or expired cookie.

    `client` is `web` or `pwa`. Any other value, or none, gives `web`, the shorter
    lifetime. `return_to` is present only when it passes `safe_return_to`.
    """
    try:
        data = _serializer(secret, _OIDC_TX_SALT).loads(value, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or not {"state", "verifier", "nonce"} <= set(data):
        return None
    tx = {k: str(data[k]) for k in ("state", "verifier", "nonce")}
    client = data.get("client")
    tx["client"] = client if client in SESSION_CLIENTS else SESSION_CLIENT_WEB
    return_to = data.get("return_to")
    checked = safe_return_to(return_to) if isinstance(return_to, str) else None
    if checked:
        tx["return_to"] = checked
    return tx


# Principal session: a server-side row with an opaque sid in a signed cookie.
# The signature age bound is the longest possible session. The row (`expires_at`) is
# the real bound, and `GET /auth/me` signs the cookie again on each app start, so an
# active session never reaches this age.
SESSION_COOKIE_MAX_AGE = MAX_SESSION_DAYS * 24 * 3600


def _sign_sid(secret: str, sid: str) -> str:
    return _serializer(secret, _SID_SALT).dumps(sid)


def _unsign_sid(secret: str, value: str, max_age: int) -> str | None:
    try:
        sid = _serializer(secret, _SID_SALT).loads(value, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return str(sid) if isinstance(sid, str) else None


def principal_sid(secret: str, cookie_value: str, max_age: int) -> str | None:
    """Return the `sid` of a principal session cookie with a valid signature.

    The check needs no database. It proves that the server issued the cookie, not
    that the session still exists. The write rate limit keys on it.
    """
    return _unsign_sid(secret, cookie_value, max_age)


async def create_principal_session(
    db: AsyncSession,
    *,
    secret: str,
    principal_id: Any,
    expires_at: Any,
    refresh_token: str | None,
    id_token: str | None,
    client: str = SESSION_CLIENT_WEB,
    now: Any = None,
) -> str:
    """Create an `auth_session` row and return the signed `sid` cookie.

    `now` is the time of the IdP check of the login (`revalidated_at`). Without it,
    the database sets the time at the insert.
    """
    sid = secrets.token_urlsafe(_SID_BYTES)
    row = AuthSession(
        sid=sid,
        principal_id=principal_id,
        expires_at=expires_at,
        refresh_token=refresh_token,
        id_token=id_token,
        client=client,
    )
    if now is not None:
        row.revalidated_at = now
    db.add(row)
    await db.flush()
    return _sign_sid(secret, sid)


async def load_principal_session(
    db: AsyncSession, *, secret: str, cookie_value: str, now: Any, max_age: int
) -> AuthSession | None:
    """Resolve a cookie to its `auth_session` row.

    Returns:
        `None` if the cookie is invalid or the row is expired.
    """
    sid = _unsign_sid(secret, cookie_value, max_age)
    if sid is None:
        return None
    row = (await db.execute(select(AuthSession).where(AuthSession.sid == sid))).scalar_one_or_none()
    if row is None or row.expires_at <= now:
        return None
    return row


async def end_principal_sessions(db: AsyncSession, principal_id: Any) -> int:
    """Delete every session of a principal and return how many ended. The caller commits.

    A session lives for months and renews itself at the IdP. So a deactivation or a
    revoke of rights must end the sessions, or an existing cookie keeps working (and,
    after a reactivation, works again).
    """
    result = await db.execute(delete(AuthSession).where(AuthSession.principal_id == principal_id))
    return result.rowcount or 0  # type: ignore[attr-defined]


async def end_other_principal_sessions(
    db: AsyncSession, principal_id: Any, keep_sid: str | None
) -> int:
    """Delete every session of a principal except the one with `keep_sid`; return the count.

    The caller commits. With `keep_sid=None` no session is kept.
    """
    statement = delete(AuthSession).where(AuthSession.principal_id == principal_id)
    if keep_sid is not None:
        statement = statement.where(AuthSession.sid != keep_sid)
    result = await db.execute(statement)
    return result.rowcount or 0  # type: ignore[attr-defined]


def sign_principal_sid(secret: str, sid: str) -> str:
    """Sign a `sid` again. The new cookie value carries a fresh signature time."""
    return _sign_sid(secret, sid)


async def delete_principal_session(
    db: AsyncSession, *, secret: str, cookie_value: str, max_age: int
) -> AuthSession | None:
    """Delete the session row on logout.

    Returns:
        The deleted row. The caller uses its `id_token` as the logout hint.
    """
    sid = _unsign_sid(secret, cookie_value, max_age)
    if sid is None:
        return None
    row = (await db.execute(select(AuthSession).where(AuthSession.sid == sid))).scalar_one_or_none()
    if row is None:
        return None
    await db.delete(row)
    await db.flush()
    return row
