"""The master howto of a format: scaffold it, or copy the howto of a readable dossier."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.archive.access import load_archive_readable
from app.modules.auth.principal import Principal
from app.modules.dossier import documents
from app.modules.dossier.models_documents import Document
from app.modules.files.access import visibility_readable
from app.modules.formats.models import Format
from app.shared.errors import ConflictError, FieldError, ValidationProblem

SCAFFOLD = "# Anleitung: {title}\n\n## Vorbereitung\n\n## Ablauf\n\n## Nachbereitung\n"


async def source_howto(
    session: AsyncSession, principal: Principal, event_id: UUID
) -> Document | None:
    """Return the howto of a dossier the caller may read, or `None` when it has none."""
    read = await load_archive_readable(session, principal, event_id)
    doc = await session.scalar(
        select(Document).where(Document.event_id == read.event.id, Document.kind == "howto")
    )
    visible = doc is not None and (
        visibility_readable(principal, read.event.organization_id, doc.visibility)
        if read.own
        else doc.visibility == "shared"
    )
    return doc if visible else None


async def create_master(
    session: AsyncSession, principal: Principal, fmt: Format, from_event_id: UUID | None
) -> Document:
    """Create the master howto of `fmt` (rev 1, shared, not verified) and link it.

    Raises:
        ConflictError: `already_exists` when the format has a master howto.
        NotFoundError: The dossier to copy from is invisible to the caller.
        ValidationProblem: `no_howto` when that dossier has no readable howto.
    """
    if fmt.master_howto_document_id is not None:
        raise ConflictError("The format has a master howto.", code="already_exists")
    title, body, meta, note = f"Anleitung {fmt.title}", SCAFFOLD.format(title=fmt.title), {}, None
    if from_event_id is not None:
        original = await source_howto(session, principal, from_event_id)
        if original is None:
            raise ValidationProblem(
                "Das Dossier hat keine lesbare Anleitung.",
                code="no_howto",
                errors=[FieldError(field="fromEventId", msg="no howto")],
            )
        title, body, meta = original.title, original.body_md, original.meta
        note = f"Aus Dossier „{original.id}“"
    doc = Document(
        format_id=fmt.id,
        kind="howto",
        title=title,
        body_md=body,
        meta=meta,
        visibility="shared",
        carry_over=True,
        created_by=principal.sub,
    )
    await documents.insert_document(session, principal, None, doc, note)
    fmt.master_howto_document_id = doc.id
    await session.flush()
    return doc
