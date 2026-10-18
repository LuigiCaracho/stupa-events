"""People endpoints for the admin: the list for I24 and the session revoke (`/admin/principals`).

Pattern from STUPA-Workflow@93c33d6 backend/app/modules/admin/principal_revoke.py
(rewritten for events roles, no code copied).
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from app.deps import DbSession, Principal, require_any_permission, require_principal
from app.modules.admin.schemas import AdminPrincipal
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.auth import sessions
from app.modules.auth.models import AuthSession
from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.schemas import RevokeResult
from app.modules.orgs.models import Membership
from app.shared.errors import NotFoundError, ProblemDetail
from app.shared.paging import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.shared.search import escape_like
from app.shared.timeutil import utcnow

router = APIRouter(prefix="/admin/principals", tags=["admin"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {401: _PROBLEM, 403: _PROBLEM, 404: _PROBLEM}
Viewer = Annotated[
    Principal, Depends(require_any_permission("admin.mappings", "admin.sessions.revoke"))
]
Revoker = Annotated[Principal, Depends(require_principal("admin.sessions.revoke"))]


@router.get("", response_model=Page[AdminPrincipal], responses=_ERRORS)
async def list_principals(
    db: DbSession,
    _: Viewer,
    group: Annotated[str | None, Query(max_length=255)] = None,
    organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AdminPrincipal]:
    """List people, filtered by cached group, organization membership or a name search."""
    open_sessions = (
        select(func.count())
        .select_from(AuthSession)
        .where(AuthSession.principal_id == PrincipalRow.id, AuthSession.expires_at > utcnow())
        .correlate(PrincipalRow)
        .scalar_subquery()
    )
    where = []
    if group:
        where.append(PrincipalRow.oidc_groups.contains([group]))
    if organization_id:
        where.append(
            PrincipalRow.id.in_(
                select(Membership.principal_id).where(Membership.organization_id == organization_id)
            )
        )
    if q:
        like = f"%{escape_like(q)}%"
        where.append(
            or_(
                PrincipalRow.display_name.ilike(like, escape="\\"),
                PrincipalRow.email.ilike(like, escape="\\"),
                PrincipalRow.sub.ilike(like, escape="\\"),
            )
        )
    total = await db.scalar(select(func.count()).select_from(PrincipalRow).where(*where))
    rows = (
        await db.execute(
            select(PrincipalRow, open_sessions)
            .where(*where)
            .order_by(PrincipalRow.display_name, PrincipalRow.sub)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    items = [
        AdminPrincipal(
            id=row.id,
            sub=row.sub,
            display_name=row.display_name,
            email=row.email,
            groups=[str(g) for g in row.oidc_groups or []],
            last_login=row.last_login,
            active=row.active,
            session_count=count,
        )
        for row, count in rows
    ]
    return Page(items=items, total=total or 0, limit=limit, offset=offset)


@router.post("/{principal_id}/sessions/revoke", response_model=RevokeResult, responses=_ERRORS)
async def revoke_sessions(db: DbSession, principal: Revoker, principal_id: UUID) -> RevokeResult:
    """End every session of a person; the next request of each session is anonymous."""
    if await db.get(PrincipalRow, principal_id) is None:
        raise NotFoundError("principal not found")
    count = await sessions.end_principal_sessions(db, principal_id)
    await audit_record(
        db,
        actor=principal.sub,
        action=AuditAction.SESSION_REVOKE,
        target_type="principal",
        target_id=str(principal_id),
        data={"scope": "admin", "count": count},
    )
    await db.commit()
    return RevokeResult(revoked=count)
