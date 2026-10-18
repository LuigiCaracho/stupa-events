"""Audit API router (``/api/admin/audit``): read the log and verify the chain.

The chain check has two forms. ``GET /verify`` computes the result live and stores
nothing. ``POST /verify`` computes the result and stores it in ``audit_verification``.
``GET /verify/latest`` reads the newest stored result without the cost of a full check.

RBAC is fail-closed. ``audit.read`` is a GLOBAL platform-wide read permission with no
organization scope; the log holds actor subs, so only the admin role has it by default.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/audit/router.py (no revert, no resolvers)
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime

from app.deps import DbSession, Principal, require_principal
from app.modules.audit.schemas import (
    AuditEntryOut,
    AuditPageOut,
    AuditVerificationOut,
    ChainVerificationOut,
)
from app.modules.audit.service import AuditService
from app.shared.errors import ProblemDetail
from app.shared.paging import DEFAULT_LIMIT, MAX_LIMIT

router = APIRouter(prefix="/admin/audit", tags=["audit"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_AUTH_ERRORS: dict[int | str, dict[str, Any]] = {401: _PROBLEM, 403: _PROBLEM}


def get_audit_service(session: DbSession) -> AuditService:
    """Build the audit service for the request session."""
    return AuditService(session)


ServiceDep = Annotated[AuditService, Depends(get_audit_service)]


@router.get(
    "",
    response_model=AuditPageOut,
    dependencies=[Depends(require_principal("audit.read"))],
    responses=_AUTH_ERRORS,
)
async def list_audit(
    service: ServiceDep,
    action: Annotated[str | None, Query()] = None,
    actor: Annotated[str | None, Query()] = None,
    since: Annotated[AwareDatetime | None, Query()] = None,
    until: Annotated[AwareDatetime | None, Query()] = None,
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> AuditPageOut:
    """Read the audit log with keyset paging, newest entry first.

    The ``before`` cursor pages backwards. Filter by ``action``, ``actor`` or the time
    window ``since``/``until``.
    """
    items, has_more = await service.query_cursor(
        action=action, actor=actor, since=since, until=until, before=before, limit=limit
    )
    return AuditPageOut(
        items=[AuditEntryOut.from_entry(e) for e in items],
        nextCursor=items[-1].id if (has_more and items) else None,
        hasMore=has_more,
    )


@router.get(
    "/verify",
    response_model=ChainVerificationOut,
    dependencies=[Depends(require_principal("audit.verify"))],
    responses=_AUTH_ERRORS,
)
async def verify_audit_chain(service: ServiceDep) -> ChainVerificationOut:
    """Recompute the hash chain and report ``valid`` plus the first break, if any."""
    result = await service.verify_chain()
    return ChainVerificationOut(
        valid=result.valid,
        checked=result.checked,
        brokenAt=result.broken_at,
        reason=result.reason,
    )


@router.post(
    "/verify",
    response_model=AuditVerificationOut,
    responses={**_AUTH_ERRORS, 409: _PROBLEM, 429: _PROBLEM},
)
async def run_audit_verification(
    service: ServiceDep,
    principal: Annotated[Principal, Depends(require_principal("audit.verify"))],
) -> AuditVerificationOut:
    """Verify the whole chain now and store the result (``trigger = manual``).

    Only one check runs at a time, and a manual check can run again only after a
    cooldown of 5 minutes.
    """
    row = await service.run_manual_verification(triggered_by=principal.sub)
    return AuditVerificationOut.from_row(row)


@router.get(
    "/verify/latest",
    response_model=AuditVerificationOut | None,
    dependencies=[Depends(require_principal("audit.read"))],
    responses=_AUTH_ERRORS,
)
async def latest_audit_verification(service: ServiceDep) -> AuditVerificationOut | None:
    """Read the newest stored chain check. ``null`` before the first check."""
    row = await service.latest_verification()
    return AuditVerificationOut.from_row(row) if row is not None else None
