"""Project the effective roles of the OIDC groups onto the `membership` table.

The IdP is the only source of a membership. The sync reads the cached
`principal.oidc_groups`, asks `rbac.effective_grants` what the groups mean (after the
downgrade of untrusted approvers) and writes `membership` to match. It reads no IdP.
Nobody else writes the table, and no decision reads it: rights come from
`Principal.has` (contract M2, 3.2 and 4). The sync never commits; the caller owns the
transaction. It runs after the principal upsert of a login or a revalidation, after a
change of a mapping or of `organization.trusted`, and for a deactivated person (empty
wish list).

Copied from STUPA-Workflow@93c33d6 backend/app/modules/admin/membership_sync.py (events roles)
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.rbac import MappingRows, grants_from, load_mappings
from app.modules.orgs.models import Membership

SYNC_ACTOR = "oidc-sync"

Wish = tuple[UUID, str]


def _wanted(mappings: MappingRows, row: PrincipalRow) -> set[Wish]:
    """Return the `(organization id, role)` pairs the person should hold."""
    if row.active is False:
        return set()
    grants = grants_from(mappings, row.oidc_groups or [])
    return {
        (grants.org_ids[slug], role) for slug, roles in grants.org_roles.items() for role in roles
    }


async def _held(db: AsyncSession, principal_id: UUID) -> set[Wish]:
    rows = await db.execute(
        select(Membership.organization_id, Membership.role).where(
            Membership.principal_id == principal_id
        )
    )
    return {(org_id, role) for org_id, role in rows.all()}


async def _audit(db: AsyncSession, principal_id: UUID, wish: Wish, change: str) -> None:
    org_id, role = wish
    await audit_record(
        db,
        actor=SYNC_ACTOR,
        action=AuditAction.ROLE_CHANGE,
        target_type="membership",
        target_id=str(org_id),
        data={"principalId": str(principal_id), "role": role, "change": change},
    )


async def sync_principal_memberships(
    db: AsyncSession, row: PrincipalRow, mappings: MappingRows | None = None
) -> bool:
    """Make the `membership` rows of one person match their groups.

    Inserts ignore a conflict, so two concurrent syncs of the same person cannot fail.

    Returns:
        `True` when a row was added or removed.
    """
    loaded = await load_mappings(db) if mappings is None else mappings
    wanted, held = _wanted(loaded, row), await _held(db, row.id)
    removed, added = sorted(held - wanted, key=str), sorted(wanted - held, key=str)
    for org_id, role in removed:
        await db.execute(
            delete(Membership).where(
                and_(
                    Membership.principal_id == row.id,
                    Membership.organization_id == org_id,
                    Membership.role == role,
                )
            )
        )
        await _audit(db, row.id, (org_id, role), "removed")
    for org_id, role in added:
        await db.execute(
            insert(Membership)
            .values(principal_id=row.id, organization_id=org_id, role=role)
            .on_conflict_do_nothing()
        )
        await _audit(db, row.id, (org_id, role), "added")
    if removed or added:
        await db.flush()
    return bool(removed or added)


async def sync_all_memberships(db: AsyncSession) -> int:
    """Run the sync for every person.

    Returns:
        The number of people whose memberships changed.
    """
    rows = (await db.execute(select(PrincipalRow).order_by(PrincipalRow.sub))).scalars().all()
    mappings = await load_mappings(db)
    return sum([await sync_principal_memberships(db, row, mappings) for row in rows])
