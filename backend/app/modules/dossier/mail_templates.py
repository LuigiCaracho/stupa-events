"""Mail templates of a dossier: a facade over `document.kind = mail_template`.

The subject and the recipient hint live in `meta`. Every save validates the template with
the catalog of `notifications.placeholders` (only `{{ path }}` expressions with a catalog
path), and the server computes `meta.placeholders`. The server never sends these mails;
the preview only renders plain text.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.dossier import documents
from app.modules.dossier.models_documents import Document
from app.modules.dossier.rules import load_for_write
from app.modules.dossier.schemas_documents import DocumentPut
from app.modules.dossier.schemas_mails import (
    MailTemplateItem,
    MailTemplateOut,
    MailTemplatePut,
    RenderPreviewIn,
    RenderPreviewOut,
)
from app.modules.notifications.placeholders import validate_template
from app.modules.notifications.preview import render_preview
from app.shared.errors import NotFoundError, ValidationProblem

_PLACEHOLDER = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def used_placeholders(*sources: str) -> list[str]:
    """Return the sorted placeholder paths a valid template uses."""
    return sorted({m for source in sources for m in _PLACEHOLDER.findall(source)})


def template_meta(subject: str, to_hint: str | None, body: str) -> dict[str, Any]:
    """Build the stored `meta` after validating subject and body."""
    validate_template(subject, body)
    meta: dict[str, Any] = {"subject": subject, "placeholders": used_placeholders(subject, body)}
    if to_hint:
        meta["toHint"] = to_hint
    return meta


def template_item(row: Document) -> MailTemplateItem:
    """Build a list entry."""
    return MailTemplateItem(
        id=row.id,
        title=row.title,
        subject=row.meta.get("subject", ""),
        visibility=row.visibility,  # type: ignore[arg-type]
        rev=row.rev,
        updated_at=row.updated_at,
    )


def template_out(row: Document) -> MailTemplateOut:
    """Build the full wire shape."""
    assert row.event_id is not None
    return MailTemplateOut(
        **template_item(row).model_dump(),
        event_id=row.event_id,
        body_md=row.body_md,
        to_hint=row.meta.get("toHint"),
        placeholders=row.meta.get("placeholders", []),
    )


async def _template(
    session: AsyncSession, principal: Principal, event_id: UUID, doc_id: UUID
) -> Document:
    row, _ = await documents.load_document(session, principal, doc_id)
    if row.event_id != event_id or row.kind != "mail_template":
        raise NotFoundError("mail template not found")
    return row


async def list_templates(
    session: AsyncSession, principal: Principal, event_id: UUID
) -> list[Document]:
    """List the readable mail templates of a dossier."""
    return await documents.list_documents(session, principal, event_id, "mail_template")


async def get_template(
    session: AsyncSession, principal: Principal, event_id: UUID, doc_id: UUID
) -> Document:
    """Return one readable mail template of the dossier."""
    return await _template(session, principal, event_id, doc_id)


async def create_template(
    session: AsyncSession, principal: Principal, event_id: UUID, body: MailTemplatePut
) -> Document:
    """Create a mail template (title required)."""
    if body.title is None:
        raise ValidationProblem("A title is required.", code="validation_error")
    event = await load_for_write(session, principal, event_id, "event.edit")
    doc = Document(
        event_id=event.id,
        kind="mail_template",
        title=body.title,
        body_md=body.body_md,
        meta=template_meta(body.subject, body.to_hint, body.body_md),
        visibility=body.visibility or "shared",
        created_by=principal.sub,
    )
    return await documents.insert_document(session, principal, event, doc)


async def save_template(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    doc_id: UUID,
    body: MailTemplatePut,
    expected_rev: int,
) -> tuple[Document, bool]:
    """Save a new version of a mail template under `If-Match`."""
    await _template(session, principal, event_id, doc_id)
    meta = template_meta(body.subject, body.to_hint, body.body_md)
    put = DocumentPut(
        title=body.title,
        body_md=body.body_md,
        change_note=body.change_note,
        visibility=body.visibility,
    )
    return await documents.save(session, principal, doc_id, put, expected_rev, meta=meta)


async def preview(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    doc_id: UUID | None,
    body: RenderPreviewIn,
) -> RenderPreviewOut:
    """Render a draft (or the stored text) against the dossier; `doc_id=None` is an unsaved one."""
    row = None if doc_id is None else await _template(session, principal, event_id, doc_id)
    event = await documents.load_readable(session, principal, event_id)
    stored_subject = "" if row is None else str(row.meta.get("subject", ""))
    subject = body.subject if body.subject is not None else stored_subject
    text = body.body_md if body.body_md is not None else ("" if row is None else row.body_md)
    rendered_subject, rendered_body = await render_preview(session, event, subject, text)
    return RenderPreviewOut(subject=rendered_subject, body=rendered_body)
