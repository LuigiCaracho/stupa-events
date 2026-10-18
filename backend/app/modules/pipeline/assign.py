"""Assign an organization to a proposal (T00 without organization, E09)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.orgs.models import Organization
from app.modules.pipeline.action_base import finish, prepare
from app.modules.pipeline.service import Fired
from app.shared.errors import ConflictError, NotFoundError


async def assign_organization(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    organization_id: UUID,
    *,
    expected_rev: int | None = None,
) -> Fired:
    """Set the organization of a dossier that has none (no commit).

    Raises:
        NotFoundError: The dossier is unreadable or the organization is unknown or inactive.
        ForbiddenError: The principal lacks `event.assign_org`.
        ConflictError: `organization_already_set`.
    """
    ctx = await prepare(session, principal, event_id, "event.assign_org", expected_rev=expected_rev)
    if ctx.event.organization_id is not None:
        raise ConflictError(
            "The dossier already has an organization.", code="organization_already_set"
        )
    organization = await session.get(Organization, organization_id)
    if organization is None or not organization.active:
        raise NotFoundError("organization not found")
    return await finish(
        session,
        ctx,
        {"organization_id": organization.id},
        audit_action=AuditAction.EVENT_ASSIGN_ORG,
        audit_data={"organizationId": str(organization.id)},
        field_class="dossier",
    )
