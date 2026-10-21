"""The checklist of a dossier: template application, items, assignees and completion.

A template resolves from the main category, else from its facts profile, else `generic`.
Applying is idempotent (`UNIQUE (event_id, template_item_id)`). Due dates follow
`checklist_due`; a date set by hand protects the item.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.principal import Principal
from app.modules.dossier import lexorank
from app.modules.dossier.checklist_due import due_at_for
from app.modules.dossier.models_checklist import (
    ChecklistItem,
    ChecklistTemplate,
    ChecklistTemplateItem,
)
from app.modules.dossier.rules import ensure_permission, load_for_write, load_readable
from app.modules.dossier.schemas_checklist import (
    ChecklistItemCreate,
    ChecklistItemOut,
    ChecklistItemPatch,
    ChecklistOut,
    TemplateRef,
)
from app.modules.events.models import Event
from app.modules.notifications.recipients import _editor_subs  # noqa: PLC2701
from app.modules.orgs.models import Membership
from app.modules.taxonomy.models import Category
from app.shared.errors import (
    ConflictError,
    FieldError,
    NotFoundError,
    ValidationProblem,
)
from app.shared.timeutil import utcnow

PHASES = ("planning", "review", "live", "followup")
WAIVER_MIN_REQUIRED = 10
EDITING_ROLES = ("submitter", "organizer")


def _is_open(item: ChecklistItem) -> bool:
    return item.done_at is None and item.waived_reason is None


async def resolve_template(
    session: AsyncSession, event: Event, slug: str | None = None
) -> ChecklistTemplate | None:
    """Return the template for a dossier: by slug, category, facts profile, else `generic`."""
    if slug is not None:
        return await session.scalar(select(ChecklistTemplate).where(ChecklistTemplate.slug == slug))
    category = (
        await session.get(Category, event.primary_category_id)
        if event.primary_category_id
        else None
    )
    if category is not None:
        by_category = await session.scalar(
            select(ChecklistTemplate).where(ChecklistTemplate.category_id == category.id)
        )
        if by_category is not None:
            return by_category
        by_profile = await session.scalar(
            select(ChecklistTemplate).where(ChecklistTemplate.profile == category.required_profile)
        )
        if by_profile is not None:
            return by_profile
    return await session.scalar(
        select(ChecklistTemplate).where(ChecklistTemplate.slug == "generic")
    )


async def _names(session: AsyncSession, subs: set[str]) -> dict[str, str | None]:
    if not subs:
        return {}
    rows = await session.execute(
        select(PrincipalRow.sub, PrincipalRow.display_name).where(PrincipalRow.sub.in_(subs))
    )
    return dict(rows.all())


def _out(item: ChecklistItem, names: dict[str, str | None]) -> ChecklistItemOut:
    now = utcnow()
    return ChecklistItemOut(
        id=item.id,
        text=item.text,
        phase=item.phase,  # type: ignore[arg-type]
        required=item.required,
        position=item.position,
        assignee_sub=item.assignee_sub,
        assignee_name=names.get(item.assignee_sub or ""),
        due_at=item.due_at,
        due_offset_days=item.due_offset_days,
        due_manual=item.due_manual,
        overdue=item.due_at is not None and item.due_at < now and _is_open(item),
        done_at=item.done_at,
        done_by=item.done_by,
        waived_reason=item.waived_reason,
        from_template=item.template_item_id is not None,
    )


async def _items(session: AsyncSession, event_id: UUID) -> list[ChecklistItem]:
    return list(
        await session.scalars(
            select(ChecklistItem)
            .where(ChecklistItem.event_id == event_id)
            .order_by(ChecklistItem.position)
        )
    )


async def _view(session: AsyncSession, event: Event, *, added: int | None = None) -> ChecklistOut:
    items = await _items(session, event.id)
    names = await _names(session, {i.assignee_sub for i in items if i.assignee_sub})
    template = await resolve_template(session, event)
    return ChecklistOut(
        items=[_out(i, names) for i in items],
        open_required={
            phase: sum(1 for i in items if i.phase == phase and i.required and _is_open(i))
            for phase in PHASES
        },
        template=TemplateRef(slug=template.slug, name=template.name) if template else None,
        added=added,
    )


async def checklist(session: AsyncSession, principal: Principal, event_id: UUID) -> ChecklistOut:
    """Return the checklist of a readable dossier."""
    return await _view(session, await load_readable(session, principal, event_id))


async def _append_position(session: AsyncSession, event_id: UUID) -> str:
    last = await session.scalar(
        select(func.max(ChecklistItem.position)).where(ChecklistItem.event_id == event_id)
    )
    return lexorank.between(last, None)


async def _audit(
    session: AsyncSession, principal: Principal, event: Event, action: str, **data: Any
) -> None:
    await audit_record(
        session,
        actor=principal.sub,
        action=AuditAction.CHECKLIST_CHANGE,
        target_type="event",
        target_id=str(event.id),
        data={"change": action, **{k: str(v) for k, v in data.items()}},
    )


async def apply_template(
    session: AsyncSession, principal: Principal, event_id: UUID, slug: str | None
) -> ChecklistOut:
    """Copy the missing items of the template into the dossier (idempotent)."""
    event = await load_for_write(session, principal, event_id, "event.edit")
    template = await resolve_template(session, event, slug)
    if template is None:
        raise NotFoundError("checklist template not found")
    rows = list(
        await session.scalars(
            select(ChecklistTemplateItem)
            .where(ChecklistTemplateItem.template_id == template.id)
            .order_by(ChecklistTemplateItem.position)
        )
    )
    have = set(
        await session.scalars(
            select(ChecklistItem.template_item_id).where(
                ChecklistItem.event_id == event.id, ChecklistItem.template_item_id.is_not(None)
            )
        )
    )
    position = await session.scalar(
        select(func.max(ChecklistItem.position)).where(ChecklistItem.event_id == event.id)
    )
    added = 0
    for row in sorted(rows, key=lambda r: (PHASES.index(r.phase), r.position)):
        if row.id in have:
            continue
        position = lexorank.between(position, None)
        session.add(
            ChecklistItem(
                event_id=event.id,
                template_item_id=row.id,
                position=position,
                text=row.text,
                phase=row.phase,
                required=row.required,
                due_offset_days=row.due_offset_days,
                due_at=due_at_for(event.starts_at, event.tzid, row.due_offset_days),
                created_by=principal.sub,
            )
        )
        added += 1
    await session.flush()
    await _audit(session, principal, event, "apply_template", template=template.slug, added=added)
    return await _view(session, event, added=added)


async def check_assignee(session: AsyncSession, event: Event, sub: str) -> None:
    """Require the assignee to be an editing member of the organization or an editor (422)."""
    member = await session.scalar(
        select(PrincipalRow.sub)
        .join(Membership, Membership.principal_id == PrincipalRow.id)
        .where(
            Membership.organization_id == event.organization_id,
            Membership.role.in_(EDITING_ROLES),
            PrincipalRow.sub == sub,
        )
    )
    if member is not None or sub in await _editor_subs(session):
        return
    raise ValidationProblem(
        "Diese Person gehört nicht zur Organisation.",
        code="assignee_not_member",
        errors=[FieldError(field="assigneeSub", msg="not a member")],
    )


async def add_item(
    session: AsyncSession, principal: Principal, event_id: UUID, body: ChecklistItemCreate
) -> ChecklistItemOut:
    """Add a free item; a `dueAt` protects it from the start rule."""
    event = await load_for_write(session, principal, event_id, "event.edit")
    if body.assignee_sub:
        await check_assignee(session, event, body.assignee_sub)
    item = ChecklistItem(
        event_id=event.id,
        position=await _append_position(session, event.id),
        text=body.text.strip(),
        phase=body.phase,
        required=body.required,
        assignee_sub=body.assignee_sub or None,
        due_at=body.due_at,
        due_manual=body.due_at is not None,
        created_by=principal.sub,
    )
    session.add(item)
    await session.flush()
    await session.refresh(item)
    await _audit(session, principal, event, "add", itemId=item.id)
    return _out(item, await _names(session, {item.assignee_sub or ""}))


async def load_item(
    session: AsyncSession, principal: Principal, item_id: UUID
) -> tuple[ChecklistItem, Event]:
    """Load an item of a readable dossier (404 otherwise)."""
    item = await session.get(ChecklistItem, item_id)
    if item is None:
        raise NotFoundError("checklist item not found")
    try:
        event = await load_readable(session, principal, item.event_id)
    except NotFoundError:
        raise NotFoundError("checklist item not found") from None
    return item, event


def _waiver(item: ChecklistItem, reason: str | None) -> None:
    text = (reason or "").strip()
    if item.done_at is not None:
        raise ConflictError("A finished item cannot be waived.", code="conflict")
    if item.required and len(text) < WAIVER_MIN_REQUIRED:
        raise ValidationProblem(
            "Pflichtpunkt kann nur mit Grund entfallen.",
            code="waiver_reason_required",
            errors=[FieldError(field="waivedReason", msg="at least 10 characters")],
        )
    item.waived_reason = text


async def patch_item(
    session: AsyncSession, principal: Principal, item_id: UUID, body: ChecklistItemPatch
) -> ChecklistItemOut:
    """Change an item; template items keep their text, phase and required flag."""
    item, event = await load_item(session, principal, item_id)
    ensure_permission(principal, event, "event.edit")
    sent = body.model_fields_set
    if item.template_item_id is not None and sent & {"text", "phase", "required"}:
        raise ConflictError(
            "A template item keeps its text, phase and required flag.", code="template_item"
        )
    was_required = item.required
    if "text" in sent and body.text is not None:
        item.text = body.text.strip()
    if "phase" in sent and body.phase is not None:
        item.phase = body.phase
    if "required" in sent and body.required is not None:
        item.required = body.required
    if "assignee_sub" in sent:
        if body.assignee_sub:
            await check_assignee(session, event, body.assignee_sub)
        item.assignee_sub = body.assignee_sub or None
    if "due_at" in sent:
        item.due_manual = body.due_at is not None
        item.due_at = body.due_at or due_at_for(event.starts_at, event.tzid, item.due_offset_days)
    if "waived_reason" in sent:
        if body.waived_reason is None or not body.waived_reason.strip():
            item.waived_reason = None
        else:
            _waiver(item, body.waived_reason)
    if "position" in sent and body.position is not None:
        try:
            lexorank.between(body.position, None)
        except lexorank.RankError as exc:
            raise ValidationProblem(
                "Invalid position.", errors=[FieldError(field="position", msg=str(exc))]
            ) from exc
        item.position = body.position
    item.updated_at = utcnow()
    await session.flush()
    await _audit(
        session,
        principal,
        event,
        "patch",
        itemId=item.id,
        **({"required": [was_required, item.required]} if was_required != item.required else {}),
    )
    return _out(item, await _names(session, {item.assignee_sub or ""}))


async def set_done(
    session: AsyncSession, principal: Principal, item_id: UUID, done: bool
) -> ChecklistItemOut:
    """Mark an item done or open again; the editors and the assignee may do it."""
    item, event = await load_item(session, principal, item_id)
    if item.assignee_sub != principal.sub:
        ensure_permission(principal, event, "event.edit")
    if done and item.waived_reason is not None:
        raise ConflictError("A waived item cannot be finished.", code="item_waived")
    item.done_at, item.done_by = (utcnow(), principal.sub) if done else (None, None)
    item.updated_at = utcnow()
    await session.flush()
    await _audit(session, principal, event, "done" if done else "undo", itemId=item.id)
    return _out(item, await _names(session, {item.assignee_sub or ""}))


async def delete_item(session: AsyncSession, principal: Principal, item_id: UUID) -> None:
    """Delete a free item (template items can only be waived)."""
    item, event = await load_item(session, principal, item_id)
    ensure_permission(principal, event, "event.edit")
    if item.template_item_id is not None:
        raise ConflictError("A template item cannot be deleted.", code="template_item")
    await session.delete(item)
    await session.flush()
    await _audit(session, principal, event, "delete", itemId=item_id)
