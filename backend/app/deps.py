"""FastAPI auth dependencies.

`get_current_principal` resolves the session cookie to an RBAC-resolved principal.
`require_principal`, `require_any_permission`, `require_any_scope` and `require_group`
raise 401 without a session and 403 when the right or the group is missing.

`Principal` comes from `app.modules.auth.principal`. That module is a leaf, so the
re-export avoids an import cycle between `deps` and `auth`.

Copied from STUPA-Workflow@93c33d6 backend/app/deps.py (cookie sessions only, org scope)
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.modules.auth import rbac, sessions
from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.principal import Principal
from app.modules.auth.session_renewal import renew_principal_session
from app.settings import Settings, get_settings
from app.shared.errors import ForbiddenError, UnauthorizedError

__all__ = [
    "DbSession",
    "Principal",
    "SettingsDep",
    "get_current_principal",
    "require_any_permission",
    "require_any_scope",
    "require_group",
    "require_principal",
]

DbSession = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_current_principal(
    request: Request,
    db: DbSession,
    settings: SettingsDep,
) -> Principal | None:
    """Resolve the principal from the session cookie.

    A long session checks the account at the IdP from time to time. The check can end
    the session, and it refreshes the groups of the row.

    Returns:
        The resolved principal, or `None` when no credential is valid.
    """
    now = datetime.now(UTC)
    cookie = request.cookies.get(settings.session_cookie_name)
    if not cookie:
        return None
    session = await sessions.load_principal_session(
        db,
        secret=settings.session_secret,
        cookie_value=cookie,
        now=now,
        max_age=sessions.SESSION_COOKIE_MAX_AGE,
    )
    if session is None:
        return None
    row = (
        await db.execute(select(PrincipalRow).where(PrincipalRow.id == session.principal_id))
    ).scalar_one_or_none()
    if row is None or row.active is False:
        return None
    if not await renew_principal_session(db, settings, session=session, principal=row, now=now):
        return None
    if row.active is False:
        return None
    return await rbac.resolve_principal(db, row, settings)


def _mark_gate(
    dependency: Callable[..., Principal], perms: tuple[str, ...] = ()
) -> Callable[..., Principal]:
    """Mark a dependency as an authorization gate, so the route inventory can find it."""
    dependency.authz_gate = True  # type: ignore[attr-defined]
    dependency.authz_perms = perms  # type: ignore[attr-defined]
    return dependency


def _authenticated(principal: Principal | None) -> Principal:
    if principal is None:
        raise UnauthorizedError("Authentication required.")
    return principal


def require_principal(*perms: str) -> Callable[..., Principal]:
    """Return a dependency: 401 without a session, 403 on a missing global permission."""

    def dependency(
        principal: Annotated[Principal | None, Depends(get_current_principal)],
    ) -> Principal:
        principal = _authenticated(principal)
        missing = [p for p in perms if not principal.has(p)]
        if missing:
            raise ForbiddenError(f"Missing permission(s): {', '.join(missing)}")
        return principal

    return _mark_gate(dependency, perms)


def require_any_permission(*perms: str) -> Callable[..., Principal]:
    """Return a dependency: 401 without a session, 403 unless ANY global permission matches."""

    def dependency(
        principal: Annotated[Principal | None, Depends(get_current_principal)],
    ) -> Principal:
        principal = _authenticated(principal)
        if not any(principal.has(p) for p in perms):
            raise ForbiddenError(f"Missing permission(s): one of {', '.join(perms)}")
        return principal

    return _mark_gate(dependency, perms)


def require_any_scope(*perms: str) -> Callable[..., Principal]:
    """Return a dependency: 401 without a session, 403 unless a `perms` entry holds somewhere.

    A right holds somewhere when it is global (a global role or the admin bypass) or
    when a role in at least one organization grants it. This is the route-level gate for
    an organization-scoped right. The service still decides on the concrete
    organization with `Principal.has(perm, org_id)`.
    """

    def dependency(
        principal: Annotated[Principal | None, Depends(get_current_principal)],
    ) -> Principal:
        principal = _authenticated(principal)
        if not any(principal.has(p) or principal.org_slugs_with(p) for p in perms):
            raise ForbiddenError(f"Missing permission: one of {', '.join(perms)}")
        return principal

    return _mark_gate(dependency, perms)


def require_group(group: str) -> Callable[..., Principal]:
    """Return a dependency: 401 without a session, 403 if the group is missing."""

    def dependency(
        principal: Annotated[Principal | None, Depends(get_current_principal)],
    ) -> Principal:
        principal = _authenticated(principal)
        if not principal.in_group(group):
            raise ForbiddenError(f"Not a member of group: {group}")
        return principal

    return _mark_gate(dependency)
