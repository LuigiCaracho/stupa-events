"""The section counters of a dossier: `GET /events/{id}/dossier-counts`.

Counters of restricted material (quotes) appear only for callers who may see it, so their
absence reveals nothing beyond the right itself.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.auth.schemas import CamelModel
from app.modules.dossier.models_checklist import ChecklistItem
from app.modules.dossier.models_comments import Comment
from app.modules.dossier.models_documents import Document
from app.modules.dossier.models_quotes import Quote
from app.modules.dossier.rules import load_readable
from app.modules.files.access import readable_clause, restricted_allowed, visibility_readable
from app.modules.files.models import Attachment


class DossierCounts(CamelModel):
    """The numbers on the sections of the dossier."""

    attachments: int
    quotes: int | None = None
    howto: int
    open_checklist: int
    mail_templates: int
    open_comments: int


async def dossier_counts(
    session: AsyncSession, principal: Principal, event_id: UUID
) -> DossierCounts:
    """Count what the caller sees in each section."""
    event = await load_readable(session, principal, event_id)
    org = event.organization_id

    async def scalar(statement) -> int:  # noqa: ANN001
        return await session.scalar(statement) or 0

    visible_docs = [v for v in ("team", "org", "shared") if visibility_readable(principal, org, v)]

    def documents(kind: str):  # noqa: ANN202
        return (
            select(func.count())
            .select_from(Document)
            .where(
                Document.event_id == event.id,
                Document.kind == kind,
                Document.visibility.in_(visible_docs),
            )
        )

    quotes = (
        await scalar(
            select(func.count())
            .select_from(Quote)
            .where(Quote.event_id == event.id, Quote.retired_at.is_(None))
        )
        if restricted_allowed(principal, org)
        else None
    )
    return DossierCounts(
        attachments=await scalar(
            select(func.count())
            .select_from(Attachment)
            .where(
                Attachment.event_id == event.id,
                Attachment.retired_at.is_(None),
                readable_clause(principal, org),
            )
        ),
        quotes=quotes,
        howto=await scalar(documents("howto")),
        open_checklist=await scalar(
            select(func.count())
            .select_from(ChecklistItem)
            .where(
                ChecklistItem.event_id == event.id,
                ChecklistItem.done_at.is_(None),
                ChecklistItem.waived_reason.is_(None),
            )
        ),
        mail_templates=await scalar(documents("mail_template")),
        open_comments=await scalar(
            select(func.count())
            .select_from(Comment)
            .where(
                Comment.event_id == event.id,
                Comment.parent_id.is_(None),
                Comment.resolved_at.is_(None),
            )
        ),
    )
