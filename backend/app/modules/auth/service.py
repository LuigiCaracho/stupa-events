"""Auth orchestration: the OIDC callback (code to token to session) and the principal upsert.

This module binds the primitives (sessions, oidc, bootstrap) to the database and the
settings. Pure HTTP wiring lives in the router. This module holds only domain logic and
I/O. It never commits: the caller owns the transaction.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/auth/service.py (magic link removed)
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.membership_sync import sync_principal_memberships
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.auth import oidc, sessions
from app.modules.auth.bootstrap import ensure_admin_for_principal
from app.modules.auth.models import SESSION_CLIENT_WEB
from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.session_renewal import session_expiry
from app.settings import Settings
from app.shared.errors import ForbiddenError
from app.shared.timeutil import utcnow

logger = logging.getLogger("app.auth")


async def upsert_principal(db: AsyncSession, claims: oidc.OidcClaims) -> PrincipalRow:
    """Create or update a principal by the OIDC `sub` (identity and group cache).

    Login and revalidation both come through here, so the membership sync runs on both.
    """
    row = (
        await db.execute(select(PrincipalRow).where(PrincipalRow.sub == claims.sub))
    ).scalar_one_or_none()
    if row is None:
        row = PrincipalRow(sub=claims.sub)
        db.add(row)
    row.email = claims.email
    row.display_name = claims.name
    row.oidc_groups = list(claims.groups)
    row.last_login = utcnow()
    await db.flush()
    await sync_principal_memberships(db, row)
    return row


async def oidc_callback(
    db: AsyncSession,
    settings: Settings,
    *,
    code: str,
    verifier: str,
    nonce: str,
    client: str = SESSION_CLIENT_WEB,
) -> tuple[str, PrincipalRow]:
    """Exchange the code, verify the token, upsert the principal and open a session.

    `client` (`web` or `pwa`) selects the session lifetime.

    Returns:
        The signed `sid` cookie value and the principal row.

    Raises:
        ForbiddenError: The account is deactivated.
    """
    token_set = await oidc.exchange_code(settings, code=code, verifier=verifier)
    claims = await oidc.verify_id_token(settings, id_token=token_set["id_token"], nonce=nonce)
    row = await upsert_principal(db, claims)
    if row.active is False:
        raise ForbiddenError("Account is deactivated.")
    await ensure_admin_for_principal(db, settings, row, email_verified=claims.email_verified)
    now = utcnow()
    cookie = await sessions.create_principal_session(
        db,
        secret=settings.session_secret,
        principal_id=row.id,
        expires_at=session_expiry(client, now),
        refresh_token=token_set.get("refresh_token"),
        id_token=token_set.get("id_token"),
        client=client,
        now=now,
    )
    await audit_record(
        db,
        actor=row.sub,
        action=AuditAction.LOGIN,
        target_type="principal",
        target_id=str(row.id),
        data={"method": "oidc"},
    )
    return cookie, row
