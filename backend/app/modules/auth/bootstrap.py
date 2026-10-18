"""Bootstrap of the initial admins.

The lists `BOOTSTRAP_ADMIN_SUBJECTS` and `BOOTSTRAP_ADMIN_EMAILS` name the first admins.
A match sets `principal.bootstrap_admin`, and the RBAC resolver then grants the global
`admin` role while the lists still name the principal. The step runs idempotently on
OIDC login and in a startup sweep. Without it a fresh installation locks itself out.
The logs carry no PII.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/auth/bootstrap.py (flag instead of role rows)
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Principal as PrincipalRow
from app.settings import Settings

logger = logging.getLogger("app.auth.bootstrap")


def _is_bootstrap_principal(row: PrincipalRow, settings: Settings, *, email_verified: bool) -> bool:
    """Return `True` if the principal matches by `sub` or by verified email.

    `sub` is the IdP identity that nobody can forge, so it always counts. An email counts
    only when `email_verified` is true. Otherwise an IdP with self-registration and no
    mail verification could issue a token with an arbitrary `email` claim.
    """
    if row.sub in settings.bootstrap_admin_subject_set:
        return True
    if not email_verified:
        return False
    return row.email is not None and row.email.lower() in settings.bootstrap_admin_email_set


async def ensure_admin_for_principal(
    db: AsyncSession, settings: Settings, row: PrincipalRow, *, email_verified: bool
) -> bool:
    """Flag this principal as bootstrap admin on the login path.

    The call is idempotent and does not commit.

    Returns:
        `True` when the call sets the flag.
    """
    if row.bootstrap_admin or not _is_bootstrap_principal(
        row, settings, email_verified=email_verified
    ):
        return False
    row.bootstrap_admin = True
    await db.flush()
    logger.info("bootstrap admin flag set on login")
    return True


async def ensure_bootstrap_admins(db: AsyncSession, settings: Settings) -> int:
    """Flag the principals named in `BOOTSTRAP_ADMIN_SUBJECTS` in a startup sweep.

    The sweep matches by `sub` only. The stored email carries no `email_verified` flag,
    so the email bootstrap happens at login with the fresh claim. The call does not
    commit.

    Returns:
        The number of newly flagged principals.
    """
    subjects = settings.bootstrap_admin_subject_set
    if not subjects:
        return 0
    rows = (
        (
            await db.execute(
                select(PrincipalRow).where(
                    PrincipalRow.sub.in_(subjects), PrincipalRow.bootstrap_admin.is_(False)
                )
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        row.bootstrap_admin = True
    if rows:
        await db.flush()
        logger.info("bootstrap admin sweep flagged %d principal(s)", len(rows))
    return len(rows)
