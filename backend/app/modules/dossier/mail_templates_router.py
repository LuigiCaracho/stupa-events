"""Mail template routes: a facade over the dossier documents of kind `mail_template`."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.dossier import mail_templates
from app.modules.dossier.documents_router import required_rev
from app.modules.dossier.schemas_mails import (
    MailTemplateItem,
    MailTemplateOut,
    MailTemplatePut,
    PlaceholderOut,
    RenderPreviewIn,
    RenderPreviewOut,
)
from app.modules.events.conflict import etag_of
from app.modules.notifications.placeholders import CATALOG
from app.shared.errors import NotFoundError, ProblemDetail

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {c: _PROBLEM for c in (401, 403, 404, 409, 422, 428)}
Reader = Annotated[Principal, Depends(require_principal("library.read"))]
Editor = Annotated[Principal, Depends(require_any_scope("event.edit"))]
IfMatch = Annotated[str | None, Header(alias="If-Match")]

router = APIRouter(tags=["mail-templates"])


@router.get(
    "/events/{event_id}/mail-templates", response_model=list[MailTemplateItem], responses=_ERRORS
)
async def list_mail_templates(
    db: DbSession, principal: Reader, event_id: UUID
) -> list[MailTemplateItem]:
    """List the mail templates of a dossier."""
    rows = await mail_templates.list_templates(db, principal, event_id)
    return [mail_templates.template_item(r) for r in rows]


@router.get(
    "/events/{event_id}/mail-templates/{doc_id}",
    response_model=MailTemplateOut,
    responses=_ERRORS,
)
async def get_mail_template(
    db: DbSession, principal: Reader, event_id: UUID, doc_id: UUID, response: Response
) -> MailTemplateOut:
    """Return a mail template with its text and its ETag."""
    row = await mail_templates.get_template(db, principal, event_id, doc_id)
    response.headers["ETag"] = etag_of(row.rev)
    return mail_templates.template_out(row)


@router.put(
    "/events/{event_id}/mail-templates/{doc_id}",
    response_model=MailTemplateOut,
    responses=_ERRORS,
)
async def put_mail_template(
    db: DbSession,
    principal: Editor,
    event_id: UUID,
    doc_id: str,
    body: MailTemplatePut,
    response: Response,
    if_match: IfMatch = None,
) -> MailTemplateOut:
    """Create (`new`) or save a mail template; unknown placeholders are a 422."""
    if doc_id == "new":
        row = await mail_templates.create_template(db, principal, event_id, body)
        response.status_code = status.HTTP_201_CREATED
    else:
        try:
            target = UUID(doc_id)
        except ValueError:
            raise NotFoundError("mail template not found") from None
        row, _ = await mail_templates.save_template(
            db, principal, event_id, target, body, required_rev(if_match)
        )
    out = mail_templates.template_out(row)
    await db.commit()
    response.headers["ETag"] = etag_of(row.rev)
    return out


@router.post(
    "/events/{event_id}/mail-templates/{doc_id}/render-preview",
    response_model=RenderPreviewOut,
    responses=_ERRORS,
)
async def render_mail_preview(
    db: DbSession, principal: Reader, event_id: UUID, doc_id: str, body: RenderPreviewIn
) -> RenderPreviewOut:
    """Render a draft or the stored template as plain text; nothing is ever sent.

    `new` renders the draft of a template that is not saved yet (the editor previews before
    the first save).
    """
    if doc_id == "new":
        return await mail_templates.preview(db, principal, event_id, None, body)
    try:
        target = UUID(doc_id)
    except ValueError:
        raise NotFoundError("mail template not found") from None
    return await mail_templates.preview(db, principal, event_id, target, body)


@router.get("/mail-template-placeholders", response_model=list[PlaceholderOut], responses=_ERRORS)
async def list_placeholders(_: Reader) -> list[PlaceholderOut]:
    """Return the placeholder catalog."""
    return [PlaceholderOut(path=p.path, label=p.label, example=p.example) for p in CATALOG]
