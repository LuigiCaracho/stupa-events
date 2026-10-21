"""Documents of a dossier: create, save with `If-Match`, history, diff and autosave drafts.

A save writes the new text into `document` and a row into `document_revision` in one
transaction. An identical save is a no-op without a revision. The autosave draft lives in
`editor_draft` (`owner_kind = document`) and never creates a revision. Images in the text
are recorded in `media_ref`; nothing is ever removed while the document lives.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.archive.access import foreign_archived
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.auth.principal import Principal
from app.modules.dossier.diff import diff_lines
from app.modules.dossier.models_documents import Document, DocumentRevision
from app.modules.dossier.rules import ensure_permission, load_for_write, load_readable
from app.modules.dossier.schemas_documents import (
    DiffOut,
    DocumentCreate,
    DocumentOut,
    DocumentPut,
    RevisionItem,
)
from app.modules.events.models import EditorDraft, Event
from app.modules.files.access import visibility_readable
from app.modules.formats.access import ensure_can_manage
from app.modules.formats.models import Format
from app.modules.media.ref_sync import (
    add_refs,
    draft_owner_id,
    drop_draft_refs,
    replace_draft_refs,
)
from app.shared.errors import ConflictError, NotFoundError
from app.shared.timeutil import utcnow

DEFAULT_VISIBILITY = {
    "howto": "shared",
    "mail_template": "shared",
    "notes": "org",
    "retrospective": "org",
}


def document_out(row: Document) -> DocumentOut:
    """Build the wire shape of a document."""
    return DocumentOut.model_validate(row)


async def load_document(
    session: AsyncSession,
    principal: Principal,
    document_id: UUID,
    *,
    lock: bool = False,
    archive: bool = False,
) -> tuple[Document, Event | None]:
    """Load a document the caller reads, with its dossier (404 otherwise).

    A master howto of a format has no dossier (`None`) and is readable for everybody who may
    read the library. With `archive` the `shared` documents of archived dossiers of other
    organizations are readable too.
    """
    query = select(Document).where(Document.id == document_id)
    row = await session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise NotFoundError("document not found")
    if row.event_id is None:
        return row, None
    try:
        event = await load_readable(session, principal, row.event_id)
    except NotFoundError:
        foreign = await foreign_archived(session, principal, row.event_id) if archive else None
        if foreign is None or row.visibility != "shared":
            raise NotFoundError("document not found") from None
        return row, foreign
    if not visibility_readable(principal, event.organization_id, row.visibility):
        raise NotFoundError("document not found")
    return row, event


async def list_documents(
    session: AsyncSession, principal: Principal, event_id: UUID, kind: str | None
) -> list[Document]:
    """List the readable documents of a dossier, newest change first, filtered in SQL."""
    event = await load_readable(session, principal, event_id)
    visible = [
        v
        for v in ("team", "org", "shared")
        if visibility_readable(principal, event.organization_id, v)
    ]
    query = select(Document).where(Document.event_id == event.id, Document.visibility.in_(visible))
    if kind is not None:
        query = query.where(Document.kind == kind)
    return list(await session.scalars(query.order_by(Document.updated_at.desc())))


async def _append(
    session: AsyncSession, doc: Document, actor: str, note: str | None, actor_type: str = "human"
) -> None:
    session.add(
        DocumentRevision(
            document_id=doc.id,
            rev=doc.rev,
            title=doc.title,
            body_md=doc.body_md,
            meta=doc.meta,
            actor_id=actor,
            actor_type=actor_type,
            change_note=note,
        )
    )
    await session.flush()


async def create(
    session: AsyncSession, principal: Principal, event_id: UUID, body: DocumentCreate
) -> Document:
    """Create a document with revision 1 (409 `already_exists` for a second howto)."""
    event = await load_for_write(session, principal, event_id, "event.edit")
    retrospective = body.kind == "retrospective"
    doc = Document(
        event_id=event.id,
        kind=body.kind,
        title=body.title,
        body_md=body.body_md,
        visibility=body.visibility or DEFAULT_VISIBILITY[body.kind],
        carry_over=False if retrospective else (body.carry_over is not False),
        created_by=principal.sub,
    )
    return await insert_document(session, principal, event, doc)


async def insert_document(
    session: AsyncSession,
    principal: Principal,
    event: Event | None,
    doc: Document,
    note: str | None = None,
) -> Document:
    """Insert a new document row with its first revision, refs and audit entry.

    Raises:
        ConflictError: `already_exists` for a second howto or retrospective of an owner.
    """
    session.add(doc)
    try:
        await session.flush()
    except IntegrityError as exc:
        if any(
            name in str(exc)
            for name in (
                "uq_document_event_howto",
                "uq_document_event_retrospective",
                "uq_document_format_howto",
            )
        ):
            raise ConflictError("The document exists already.", code="already_exists") from exc
        raise
    await session.refresh(doc)
    await _append(session, doc, principal.sub, note)
    await add_refs(session, "document", doc.id, doc.body_md)
    await audit_record(
        session,
        actor=principal.sub,
        action=AuditAction.DOCUMENT_CREATE,
        target_type="document",
        target_id=str(doc.id),
        data={**_owner(event, doc), "kind": doc.kind},
    )
    return doc


def _owner(event: Event | None, doc: Document) -> dict[str, str]:
    return {"eventId": str(event.id)} if event is not None else {"formatId": str(doc.format_id)}


async def authorize_write(
    session: AsyncSession, principal: Principal, doc: Document, event: Event | None
) -> None:
    """Check the right to change a document: the dossier rules, or the right on its format."""
    if event is None:
        fmt = await session.get(Format, doc.format_id)
        assert fmt is not None
        await ensure_can_manage(session, principal, fmt)
        return
    ensure_permission(principal, event, "event.edit")


def _current(doc: Document) -> dict[str, Any]:
    return {"current": document_out(doc).model_dump(by_alias=True, mode="json")}


async def save(
    session: AsyncSession,
    principal: Principal,
    document_id: UUID,
    body: DocumentPut,
    expected_rev: int,
    *,
    meta: dict[str, Any] | None = None,
) -> tuple[Document, bool]:
    """Save a new version under `If-Match`; return the document and whether it changed.

    Raises:
        ConflictError: 409 `conflict` with `current` when the revision moved on, or 409
            `use_mail_templates` for a mail template saved without its validated `meta`.
    """
    doc, event = await load_document(session, principal, document_id, lock=True)
    await authorize_write(session, principal, doc, event)
    if doc.kind == "mail_template" and meta is None:
        raise ConflictError(
            "A mail template is saved through the mail template routes.",
            code="use_mail_templates",
        )
    if doc.rev != expected_rev:
        raise ConflictError(
            "The document was changed in the meantime.", code="conflict", extensions=_current(doc)
        )
    title = body.title if body.title is not None else doc.title
    visibility = body.visibility or doc.visibility
    carry = doc.carry_over if body.carry_over is None else body.carry_over
    new_meta = doc.meta if meta is None else meta
    unchanged = (title, body.body_md, visibility, carry, new_meta) == (
        doc.title,
        doc.body_md,
        doc.visibility,
        doc.carry_over,
        doc.meta,
    )
    if unchanged:
        return doc, False
    doc.title, doc.body_md, doc.visibility, doc.carry_over, doc.meta = (
        title,
        body.body_md,
        visibility,
        carry,
        new_meta,
    )
    doc.rev += 1
    doc.updated_at = utcnow()
    await _append(session, doc, principal.sub, (body.change_note or "").strip() or None)
    await add_refs(session, "document", doc.id, doc.body_md)
    await audit_record(
        session,
        actor=principal.sub,
        action=AuditAction.DOCUMENT_UPDATE,
        target_type="document",
        target_id=str(doc.id),
        data={**_owner(event, doc), "rev": doc.rev},
    )
    return doc, True


async def revisions(
    session: AsyncSession, principal: Principal, document_id: UUID
) -> list[RevisionItem]:
    """List the revisions newest first with the change against their predecessor."""
    doc, _ = await load_document(session, principal, document_id)
    rows = list(
        await session.scalars(
            select(DocumentRevision)
            .where(DocumentRevision.document_id == doc.id)
            .order_by(DocumentRevision.rev)
        )
    )
    items = []
    previous: DocumentRevision | None = None
    for row in rows:
        items.append(
            RevisionItem(
                rev=row.rev,
                actor_id=row.actor_id,
                actor_type=row.actor_type,
                change_note=row.change_note,
                at=row.at,
                title_changed=previous is not None and previous.title != row.title,
                chars_delta=len(row.body_md) - (len(previous.body_md) if previous else 0),
            )
        )
        previous = row
    return items[::-1]


async def get_revision(
    session: AsyncSession, principal: Principal, document_id: UUID, rev: int
) -> DocumentRevision:
    """Return one revision of a readable document (404 for an unknown one)."""
    doc, _ = await load_document(session, principal, document_id)
    row = await session.get(DocumentRevision, (doc.id, rev))
    if row is None:
        raise NotFoundError("revision not found")
    return row


async def diff(
    session: AsyncSession, principal: Principal, document_id: UUID, from_rev: int, to_rev: int
) -> DiffOut:
    """Compare the texts of two revisions line by line."""
    old = await get_revision(session, principal, document_id, from_rev)
    new = await get_revision(session, principal, document_id, to_rev)
    lines = diff_lines(old.body_md, new.body_md)
    return DiffOut.model_validate(
        {
            "from": from_rev,
            "to": to_rev,
            "lines": lines,
            "added": sum(line.op == "add" for line in lines),
            "removed": sum(line.op == "remove" for line in lines),
        }
    )


async def put_draft(
    session: AsyncSession,
    principal: Principal,
    document_id: UUID,
    base_rev: int,
    body_md: str,
    title: str | None,
) -> EditorDraft:
    """Store the caller's autosave draft (no revision, no audit)."""
    doc, event = await load_document(session, principal, document_id)
    await authorize_write(session, principal, doc, event)
    fields = {"bodyMd": body_md, **({"title": title} if title is not None else {})}
    stmt = insert(EditorDraft).values(
        owner_kind="document",
        owner_id=doc.id,
        principal_sub=principal.sub,
        base_rev=base_rev,
        fields=fields,
        updated_at=utcnow(),
    )
    row = await session.scalar(
        stmt.on_conflict_do_update(
            index_elements=["owner_kind", "owner_id", "principal_sub"],
            set_={
                "base_rev": stmt.excluded.base_rev,
                "fields": stmt.excluded.fields,
                "updated_at": stmt.excluded.updated_at,
            },
        ).returning(EditorDraft)
    )
    assert row is not None
    await replace_draft_refs(session, draft_owner_id(doc.id, principal.sub), body_md)
    return row


async def get_draft(
    session: AsyncSession, principal: Principal, document_id: UUID
) -> EditorDraft | None:
    """Return the caller's own draft of a readable document, or `None`."""
    doc, _ = await load_document(session, principal, document_id)
    return await session.scalar(
        select(EditorDraft).where(
            EditorDraft.owner_kind == "document",
            EditorDraft.owner_id == doc.id,
            EditorDraft.principal_sub == principal.sub,
        )
    )


async def delete_draft(session: AsyncSession, principal: Principal, document_id: UUID) -> None:
    """Discard the caller's draft and its image references."""
    doc, _ = await load_document(session, principal, document_id)
    await session.execute(
        delete(EditorDraft).where(
            EditorDraft.owner_kind == "document",
            EditorDraft.owner_id == doc.id,
            EditorDraft.principal_sub == principal.sub,
        )
    )
    await drop_draft_refs(session, draft_owner_id(doc.id, principal.sub))
