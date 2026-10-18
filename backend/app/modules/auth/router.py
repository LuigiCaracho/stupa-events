"""Auth endpoints: OIDC login and callback (auth code plus PKCE), logout and `/auth/me`.

A token never reaches JavaScript or the response body. The server sends the session only
in an HttpOnly, SameSite=Lax cookie.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/auth/router.py (magic link and OAuth removed)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.deps import DbSession, Principal, SettingsDep, require_principal
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.auth import oidc, service, sessions
from app.modules.auth.models import SESSION_CLIENT_WEB, session_days
from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.oidc import OidcError, OidcUnavailableError
from app.modules.auth.schemas import LogoutOut, MeOrganization, MeOut, RevokeResult
from app.modules.orgs.scope import org_refs
from app.settings import Settings
from app.shared.errors import (
    BadRequestError,
    NotFoundError,
    ProblemDetail,
    ServiceUnavailableError,
)
from app.shared.permissions import permissions_of

logger = logging.getLogger("app.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_TX_MAX_AGE = 600


def _errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    """Document problem+json for the given error status codes."""
    return {code: _PROBLEM for code in codes}


def _cookie_kwargs(settings: SettingsDep) -> dict[str, object]:
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "path": "/",
    }


@router.get(
    "/login",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    responses=_errors(404, 503),
)
async def login(
    settings: SettingsDep,
    client: Annotated[Literal["web", "pwa"], Query()] = SESSION_CLIENT_WEB,
    return_to: Annotated[str | None, Query(alias="returnTo", max_length=2048)] = None,
) -> RedirectResponse:
    """Redirect to the IdP with the auth code flow and PKCE.

    The tx cookie carries the state, the code verifier, the nonce and the client.
    `client=pwa` comes from the installed app and selects the longer session lifetime.
    `returnTo` is the path of the app where the login started; a value that is not a
    same-origin path of the app (`sessions.safe_return_to`) is dropped.
    """
    if not settings.oidc_enabled:
        raise NotFoundError("OIDC is not configured.")
    verifier, challenge = oidc.generate_pkce()
    state = oidc.generate_state()
    nonce = oidc.generate_nonce()
    try:
        url = await oidc.authorization_url(settings, state=state, challenge=challenge, nonce=nonce)
    except OidcError as exc:
        raise ServiceUnavailableError("The identity provider is unavailable.") from exc
    response = RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    response.set_cookie(
        settings.oidc_tx_cookie_name,
        sessions.issue_oidc_tx(
            settings.session_secret,
            state,
            verifier,
            nonce,
            client,
            sessions.safe_return_to(return_to),
        ),
        max_age=_TX_MAX_AGE,
        **_cookie_kwargs(settings),  # type: ignore[arg-type]
    )
    return response


@router.get(
    "/callback",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    responses=_errors(400, 404, 503),
)
async def callback(
    request: Request,
    db: DbSession,
    settings: SettingsDep,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
) -> RedirectResponse:
    """Exchange the code for a token and open a session.

    The state match and the nonce in the id_token protect against CSRF and replay. An
    IdP that cannot be reached gives 503. A rejected code or token gives 400.
    """
    if not settings.oidc_enabled:
        raise NotFoundError("OIDC is not configured.")
    tx_cookie = request.cookies.get(settings.oidc_tx_cookie_name)
    tx = (
        sessions.load_oidc_tx(settings.session_secret, tx_cookie, _TX_MAX_AGE)
        if tx_cookie
        else None
    )
    if tx is None or tx["state"] != state:
        raise BadRequestError("Invalid or expired OIDC transaction.")
    try:
        cookie, _ = await service.oidc_callback(
            db,
            settings,
            code=code,
            verifier=tx["verifier"],
            nonce=tx["nonce"],
            client=tx["client"],
        )
    except OidcUnavailableError as exc:
        raise ServiceUnavailableError("The identity provider is unavailable.") from exc
    except OidcError as exc:
        raise BadRequestError("OIDC login failed.") from exc
    await db.commit()

    dest = settings.public_base_url
    if tx.get("return_to"):
        dest = settings.public_base_url.rstrip("/") + tx["return_to"]
    response = RedirectResponse(dest, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    response.set_cookie(
        settings.session_cookie_name,
        cookie,
        max_age=session_days(tx["client"]) * 24 * 3600,
        **_cookie_kwargs(settings),  # type: ignore[arg-type]
    )
    response.delete_cookie(settings.oidc_tx_cookie_name, path="/")
    return response


@router.post("/logout")
async def logout(
    request: Request, db: DbSession, settings: SettingsDep, response: Response
) -> LogoutOut:
    """End the server session and clear the cookie.

    The route is idempotent.

    Returns:
        For OIDC, the RP-initiated logout URL (the `end_session_endpoint` of the IdP
        with `id_token_hint`), or `None` when the IdP has none or its discovery
        document is unusable. The local session ends in every case.
    """
    logout_url: str | None = None
    cookie = request.cookies.get(settings.session_cookie_name)
    if cookie:
        ended = await sessions.delete_principal_session(
            db,
            secret=settings.session_secret,
            cookie_value=cookie,
            max_age=sessions.SESSION_COOKIE_MAX_AGE,
        )
        if settings.oidc_enabled and ended is not None:
            try:
                logout_url = await oidc.end_session_url(settings, id_token=ended.id_token)
            except OidcError:
                logger.warning("oidc discovery failed at logout, no IdP logout URL")
    await db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    return LogoutOut(logout_url=logout_url)


async def _renew_session_cookie(
    request: Request, response: Response, db: DbSession, settings: Settings
) -> None:
    """Sign the session cookie again and align its lifetime with the session row.

    The app calls `/auth/me` on each start. The session row slides at each check at the
    IdP, but the browser keeps the cookie only for its own `max_age`. This step carries
    the new end over to the cookie and renews the signature time.
    """
    cookie = request.cookies.get(settings.session_cookie_name)
    if not cookie:
        return
    now = datetime.now(UTC)
    row = await sessions.load_principal_session(
        db,
        secret=settings.session_secret,
        cookie_value=cookie,
        now=now,
        max_age=sessions.SESSION_COOKIE_MAX_AGE,
    )
    if row is None:
        return
    response.set_cookie(
        settings.session_cookie_name,
        sessions.sign_principal_sid(settings.session_secret, row.sid),
        max_age=max(int((row.expires_at - now).total_seconds()), 0),
        **_cookie_kwargs(settings),  # type: ignore[arg-type]
    )


@router.get("/me", responses=_errors(401))
async def me(
    request: Request,
    response: Response,
    principal: Annotated[Principal, Depends(require_principal())],
    db: DbSession,
    settings: SettingsDep,
) -> MeOut:
    """Return the principal plus the resolved roles, permissions, groups and organizations.

    The organizations carry their name, short name and `trusted` flag from one query
    (`org_refs`). The response also renews the session cookie (see `_renew_session_cookie`).
    """
    await _renew_session_cookie(request, response, db, settings)
    refs = await org_refs(db, principal)
    return MeOut(
        sub=principal.sub,
        email=principal.email,
        display_name=principal.display_name,
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions | _org_permissions(principal)),
        groups=sorted(principal.groups),
        organizations=[
            MeOrganization(
                slug=slug,
                role=role,
                organization_id=refs[slug].id,
                name=refs[slug].name,
                short=refs[slug].short,
                trusted=refs[slug].trusted,
            )
            for slug, role in principal.organizations
            if slug in refs
        ],
    )


def _org_permissions(principal: Principal) -> set[str]:
    """Collect the permissions that any organization role grants (for the UI only)."""
    return set().union(*(permissions_of(roles) for roles in principal.org_roles.values()))


@router.post(
    "/sessions/revoke",
    response_model=RevokeResult,
    responses=_errors(401),
)
async def revoke_other_sessions(
    request: Request,
    principal: Annotated[Principal, Depends(require_principal())],
    db: DbSession,
    settings: SettingsDep,
) -> RevokeResult:
    """End every other session of the caller; the running session stays.

    Rights come from the IdP groups and are read afresh at the next login, so this is the
    way to make a session that predates a withdrawal in the IdP log in again at once.
    """
    row = (
        await db.execute(select(PrincipalRow).where(PrincipalRow.sub == principal.sub))
    ).scalar_one_or_none()
    if row is None:
        return RevokeResult(revoked=0)
    current = request.cookies.get(settings.session_cookie_name)
    keep = (
        await sessions.load_principal_session(
            db,
            secret=settings.session_secret,
            cookie_value=current,
            now=datetime.now(UTC),
            max_age=sessions.SESSION_COOKIE_MAX_AGE,
        )
        if current
        else None
    )
    count = await sessions.end_other_principal_sessions(db, row.id, keep.sid if keep else None)
    await audit_record(
        db,
        actor=principal.sub,
        action=AuditAction.SESSION_REVOKE,
        target_type="principal",
        target_id=str(row.id),
        data={"scope": "own", "count": count},
    )
    await db.commit()
    return RevokeResult(revoked=count)
