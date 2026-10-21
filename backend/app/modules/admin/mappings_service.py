"""Group mapping service: list, create, change, delete and the default proposal.

Every mutation validates the pair (`mappings.validate_mapping`), runs the membership sync
and writes `ROLE_MAPPING_CHANGE` in the caller's transaction. The service never commits.
Group names are not personal data, so the audit `data` may carry them.

Pattern from STUPA-Workflow@93c33d6 backend/app/modules/admin/oidc_mappings.py
(rewritten for events roles, no code copied).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.mappings import MappingIssue, OrgFacts, validate_group, validate_mapping
from app.modules.admin.membership_sync import sync_all_memberships
from app.modules.admin.schemas import (
    GroupMappingCreate,
    GroupMappingOut,
    GroupMappingPatch,
)
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.auth.models import Principal as PrincipalRow
from app.modules.orgs.models import GroupMapping, Organization
from app.modules.orgs.schemas import OrgRef
from app.settings import Settings
from app.shared.errors import ConflictError, FieldError, NotFoundError, ValidationProblem
from app.shared.permissions import default_mappings


def _refuse(issues: list[MappingIssue]) -> ValidationProblem:
    return ValidationProblem(
        "Invalid group mapping.",
        code=issues[0].code,
        errors=[FieldError(field=i.field, msg=i.msg) for i in issues],
    )


class MappingService:
    """Operations on `group_mapping` for one request session."""

    def __init__(self, session: AsyncSession, settings: Settings, actor: str) -> None:
        self.session = session
        self.settings = settings
        self._actor = actor

    async def _out(self, rows: list[tuple[GroupMapping, Organization | None, int]]):
        return [
            GroupMappingOut(
                id=mapping.id,
                oidc_group=mapping.oidc_group,
                role=mapping.role,  # type: ignore[arg-type]
                organization=OrgRef.model_validate(org) if org else None,
                principal_count=count,
                created_at=mapping.created_at,
                updated_at=mapping.updated_at,
            )
            for mapping, org, count in rows
        ]

    def _query(self):
        count = (
            select(func.count())
            .select_from(PrincipalRow)
            .where(
                PrincipalRow.oidc_groups.contains(func.jsonb_build_array(GroupMapping.oidc_group))
            )
            .correlate(GroupMapping)
            .scalar_subquery()
        )
        return select(GroupMapping, Organization, count).outerjoin(
            Organization, Organization.id == GroupMapping.organization_id
        )

    async def list(self) -> list[GroupMappingOut]:
        """List all mappings, sorted by group."""
        rows = (await self.session.execute(self._query().order_by(GroupMapping.oidc_group))).all()
        return await self._out([tuple(r) for r in rows])  # type: ignore[arg-type]

    async def _one(self, mapping_id: UUID) -> GroupMappingOut:
        row = (await self.session.execute(self._query().where(GroupMapping.id == mapping_id))).one()
        return (await self._out([tuple(row)]))[0]  # type: ignore[arg-type]

    async def _facts(self, organization_id: UUID | None) -> OrgFacts | None:
        org = await self.session.get(Organization, organization_id) if organization_id else None
        return OrgFacts(active=org.active) if org else None

    async def _audit(self, mapping: GroupMapping, change: str) -> None:
        await audit_record(
            self.session,
            actor=self._actor,
            action=AuditAction.ROLE_MAPPING_CHANGE,
            target_type="group_mapping",
            target_id=str(mapping.id),
            data={
                "oidcGroup": mapping.oidc_group,
                "role": mapping.role,
                "organizationId": str(mapping.organization_id) if mapping.organization_id else None,
                "change": change,
            },
        )

    async def create(self, body: GroupMappingCreate) -> GroupMappingOut:
        """Create a mapping.

        Raises:
            ValidationProblem: A rule of `validate_mapping` or the reserved prefix.
            ConflictError: The group is mapped already (`duplicate_group`).
        """
        issues = validate_group(body.oidc_group) + validate_mapping(
            body.role, body.organization_id, await self._facts(body.organization_id)
        )
        if issues:
            raise _refuse(issues)
        taken = await self.session.scalar(
            select(GroupMapping.id).where(GroupMapping.oidc_group == body.oidc_group)
        )
        if taken is not None:
            raise ConflictError("This group is mapped already.", code="duplicate_group")
        mapping = GroupMapping(
            oidc_group=body.oidc_group, role=body.role, organization_id=body.organization_id
        )
        self.session.add(mapping)
        await self.session.flush()
        await self.session.refresh(mapping)
        await self._audit(mapping, "created")
        await sync_all_memberships(self.session)
        return await self._one(mapping.id)

    async def _get(self, mapping_id: UUID) -> GroupMapping:
        mapping = await self.session.get(GroupMapping, mapping_id)
        if mapping is None:
            raise NotFoundError("group mapping not found")
        return mapping

    async def _guard_last_admin(self, mapping: GroupMapping, new_role: str | None) -> None:
        if mapping.role != "admin" or new_role == "admin":
            return
        if self.settings.bootstrap_admin_subject_set or self.settings.bootstrap_admin_email_set:
            return
        admins = await self.session.scalar(
            select(func.count()).select_from(GroupMapping).where(GroupMapping.role == "admin")
        )
        if admins == 1:
            raise ConflictError("The last admin mapping stays.", code="last_admin_mapping")

    async def update(self, mapping_id: UUID, body: GroupMappingPatch) -> GroupMappingOut:
        """Change the role or the organization of a mapping."""
        mapping = await self._get(mapping_id)
        role = body.role or mapping.role
        org_id = (
            body.organization_id
            if "organization_id" in body.model_fields_set
            else mapping.organization_id
        )
        issues = validate_mapping(role, org_id, await self._facts(org_id))
        if issues:
            raise _refuse(issues)
        await self._guard_last_admin(mapping, role)
        mapping.role, mapping.organization_id = role, org_id
        await self.session.flush()
        await self.session.refresh(mapping)
        await self._audit(mapping, "updated")
        await sync_all_memberships(self.session)
        return await self._one(mapping.id)

    async def delete(self, mapping_id: UUID) -> None:
        """Delete a mapping (`last_admin_mapping` protects the last admin row)."""
        mapping = await self._get(mapping_id)
        await self._guard_last_admin(mapping, None)
        await self._audit(mapping, "deleted")
        await self.session.delete(mapping)
        await self.session.flush()
        await sync_all_memberships(self.session)

    async def create_defaults(self) -> list[GroupMappingOut]:
        """Create the proposed mappings that do not exist yet (idempotent)."""
        orgs = (
            (await self.session.execute(select(Organization).where(Organization.active.is_(True))))
            .scalars()
            .all()
        )
        by_slug = {org.slug: org for org in orgs}
        known = set((await self.session.scalars(select(GroupMapping.oidc_group))).all())
        created: list[GroupMapping] = []
        for spec in default_mappings(org.slug for org in orgs):
            if spec.group in known:
                continue
            mapping = GroupMapping(
                oidc_group=spec.group,
                role=spec.role,
                organization_id=by_slug[spec.org].id if spec.org else None,
            )
            self.session.add(mapping)
            created.append(mapping)
        await self.session.flush()
        for mapping in created:
            await self._audit(mapping, "created")
        if created:
            await sync_all_memberships(self.session)
        return [await self._one(mapping.id) for mapping in created]
