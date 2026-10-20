"""Review comments: threads with optional anchors, resolving and the open counts.

A root comment may point at a field (`hero` for the poster), an attachment, a checklist item
or a text range of a document revision. Replies hang under a root and carry no anchor. The
guards read the open root comments (`open_comments`, `open_hero_comments` in
`dossier.guard_data`). Comments never appear in `event_revision`. They are never edited or
deleted; resolving only sets `resolved_at/by` (the table trigger enforces it).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.principal import Principal
from app.modules.dossier.models_checklist import ChecklistItem
from app.modules.dossier.models_comments import Comment
from app.modules.dossier.models_documents import Document, DocumentRevision
from app.modules.dossier.rules import load_readable
from app.modules.dossier.schemas_comments import CommentCreate, CommentOut, ThreadOut
from app.modules.events.models import Event
from app.modules.files.access import attachment_readable
from app.modules.files.models import Attachment
from app.modules.media.ref_sync import add_refs
from app.modules.notifications.service import PendingMail, notify, notify_event
from app.modules.pipeline.guards.common import FIELD_NAMES
from app.shared.errors import (
    ConflictError,
    FieldError,
    ForbiddenError,
    NotFoundError,
    ValidationProblem,
)
from app.shared.timeutil import utcnow

HERO = "hero"
ALLOWED_FIELDS = frozenset({HERO, *FIELD_NAMES, *FIELD_NAMES.values()})
_ANCHOR_KEYS = frozenset({"field", "attachmentId", "checklistItemId", "documentId"})


def _invalid(message: str) -> ValidationProblem:
    return ValidationProblem(
        message, code="anchor_invalid", errors=[FieldError(field="anchor", msg=message)]
    )


async def _check_range(session: AsyncSession, event_id: UUID, anchor: dict[str, Any]) -> None:
    try:
        document_id, rev = UUID(str(anchor["documentId"])), int(anchor["rev"])
        start, end = int(anchor["from"]), int(anchor["to"])
    except (KeyError, ValueError, TypeError) as exc:
        raise _invalid("A document anchor needs documentId, rev, from and to.") from exc
    doc = await session.get(Document, document_id)
    revision = await session.get(DocumentRevision, (document_id, rev))
    if doc is None or doc.event_id != event_id or revision is None:
        raise _invalid("The document anchor points to a foreign or unknown document.")
    if not 0 <= start < end <= len(revision.body_md):
        raise _invalid("The offsets of the document anchor are out of range.")


async def validate_anchor(
    session: AsyncSession, event_id: UUID, anchor: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Check an anchor against the dossier and return it (422 `anchor_invalid`)."""
    if anchor is None:
        return None
    keys = _ANCHOR_KEYS & set(anchor)
    if len(keys) != 1:
        raise _invalid("An anchor names exactly one target.")
    key = next(iter(keys))
    if key == "field":
        if anchor.get("field") not in ALLOWED_FIELDS or set(anchor) != {"field"}:
            raise _invalid("Unknown field.")
    elif key == "documentId":
        await _check_range(session, event_id, anchor)
    else:
        model = Attachment if key == "attachmentId" else ChecklistItem
        try:
            target = await session.get(model, UUID(str(anchor[key])))
        except ValueError as exc:
            raise _invalid("The anchor id is not valid.") from exc
        if target is None or target.event_id != event_id or set(anchor) != {key}:
            raise _invalid("The anchor points to a foreign or unknown object.")
    return anchor


async def _names(session: AsyncSession, subs: set[str]) -> dict[str, str | None]:
    if not subs:
        return {}
    rows = await session.execute(
        select(PrincipalRow.sub, PrincipalRow.display_name).where(PrincipalRow.sub.in_(subs))
    )
    return dict(rows.all())


def _out(row: Comment, names: dict[str, str | None]) -> CommentOut:
    return CommentOut(
        id=row.id,
        author_sub=row.author_sub,
        author_name=names.get(row.author_sub),
        actor_type=row.actor_type,
        body_md=row.body_md,
        anchor=row.anchor,
        parent_id=row.parent_id,
        resolved_at=row.resolved_at,
        resolved_by=row.resolved_by,
        created_at=row.created_at,
    )


async def _visible(
    session: AsyncSession, principal: Principal, event: Event, rows: list[Comment]
) -> list[Comment]:
    """Drop the threads anchored on an attachment that the caller may not see."""
    anchored = {
        UUID(str(r.anchor["attachmentId"])) for r in rows if r.anchor and "attachmentId" in r.anchor
    }
    if not anchored:
        return rows
    files = await session.scalars(select(Attachment).where(Attachment.id.in_(anchored)))
    hidden = {
        f.id
        for f in files
        if not attachment_readable(principal, event.organization_id, f.kind, f.visibility)
    }
    hidden_roots = {
        r.id for r in rows if r.anchor and UUID(str(r.anchor.get("attachmentId", r.id))) in hidden
    }
    return [r for r in rows if r.id not in hidden_roots and r.parent_id not in hidden_roots]


async def threads(
    session: AsyncSession, principal: Principal, event_id: UUID, *, only_open: bool
) -> list[ThreadOut]:
    """Return the root comments with their replies, newest root first."""
    event = await load_readable(session, principal, event_id)
    rows = list(
        await session.scalars(
            select(Comment).where(Comment.event_id == event.id).order_by(Comment.created_at)
        )
    )
    rows = await _visible(session, principal, event, rows)
    names = await _names(session, {r.author_sub for r in rows})
    replies: dict[UUID, list[CommentOut]] = {}
    for row in rows:
        if row.parent_id is not None:
            replies.setdefault(row.parent_id, []).append(_out(row, names))
    roots = [r for r in rows if r.parent_id is None and not (only_open and r.resolved_at)]
    return [
        ThreadOut(**_out(r, names).model_dump(), replies=replies.get(r.id, []))
        for r in reversed(roots)
    ]


async def create(
    session: AsyncSession, principal: Principal, event_id: UUID, body: CommentCreate
) -> tuple[Comment, CommentOut, list[PendingMail]]:
    """Add a comment or a reply and notify the dossier's people (no commit)."""
    event = await load_readable(session, principal, event_id)
    if not principal.has("comment.write", event.organization_id):
        raise ForbiddenError("Missing permission: comment.write")
    if body.parent_id is not None:
        parent = await session.get(Comment, body.parent_id)
        if parent is None or parent.event_id != event.id:
            raise NotFoundError("comment not found")
        if parent.parent_id is not None or body.anchor is not None:
            raise _invalid("A reply goes under a root comment and carries no anchor.")
    anchor = await validate_anchor(session, event.id, body.anchor)
    row = Comment(
        event_id=event.id,
        parent_id=body.parent_id,
        author_sub=principal.sub,
        body_md=body.body_md,
        anchor=anchor,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    await add_refs(session, "comment", row.id, row.body_md)
    await audit_record(
        session,
        actor=principal.sub,
        action=AuditAction.COMMENT_CREATE,
        target_type="comment",
        target_id=str(row.id),
        data={"eventId": str(event.id), "reply": body.parent_id is not None},
    )
    pending = await notify_event(
        session,
        "comment_added",
        event,
        {"actorName": principal.display_name or "Jemand"},
        actor_sub=principal.sub,
    )
    return row, _out(row, {principal.sub: principal.display_name}), pending


async def _toggle(
    session: AsyncSession, principal: Principal, comment_id: UUID, *, resolve: bool
) -> tuple[Comment, Event, bool]:
    row = await session.get(Comment, comment_id, with_for_update=True)
    if row is None:
        raise NotFoundError("comment not found")
    try:
        event = await load_readable(session, principal, row.event_id)
    except NotFoundError:
        raise NotFoundError("comment not found") from None
    if row.parent_id is not None:
        raise ConflictError("Only a root comment can be resolved.", code="not_a_root")
    if not (
        row.author_sub == principal.sub or principal.has("event.approve", event.organization_id)
    ):
        raise ForbiddenError("Only the author or an approver may do this.")
    changed = (row.resolved_at is not None) != resolve
    if changed:
        row.resolved_at, row.resolved_by = (utcnow(), principal.sub) if resolve else (None, None)
        await session.flush()
        await audit_record(
            session,
            actor=principal.sub,
            action=AuditAction.COMMENT_RESOLVE if resolve else AuditAction.COMMENT_REOPEN,
            target_type="comment",
            target_id=str(row.id),
            data={"eventId": str(event.id)},
        )
    return row, event, changed


async def resolve(
    session: AsyncSession, principal: Principal, comment_id: UUID
) -> tuple[CommentOut, list[PendingMail]]:
    """Resolve a root comment (idempotent) and tell its author when someone else did."""
    row, event, changed = await _toggle(session, principal, comment_id, resolve=True)
    pending: list[PendingMail] = []
    if changed and row.author_sub != principal.sub:
        pending = await notify(
            session,
            "comment_resolved",
            [row.author_sub],
            event,
            {"actorName": principal.display_name or "Jemand"},
            actor_sub=principal.sub,
        )
    return _out(row, await _names(session, {row.author_sub})), pending


async def reopen(session: AsyncSession, principal: Principal, comment_id: UUID) -> CommentOut:
    """Reopen a resolved root comment."""
    row, _, _ = await _toggle(session, principal, comment_id, resolve=False)
    return _out(row, await _names(session, {row.author_sub}))
