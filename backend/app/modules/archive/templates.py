"""The template list (`GET /api/templates`): clonable dossiers found by the shared search query."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.archive.schemas import TemplateCard
from app.modules.auth.principal import Principal
from app.modules.formats.queries import OrgBrief
from app.modules.formats.schemas import FormatRef
from app.modules.search import query
from app.modules.search.filters import Filters, reader_of
from app.modules.search.words import parse
from app.modules.taxonomy.schemas import CategoryRef


def card_of(row: Row[Any]) -> TemplateCard:
    """Shape one row of the template query into a card."""
    return TemplateCard(
        id=row.id,
        title=row.title,
        starts_at=row.starts_at,
        all_day=row.all_day,
        state=row.state,
        organization=OrgBrief(slug=row.org_slug, name=row.org_name, short=row.org_short),
        format=FormatRef(slug=row.fmt_slug, title=row.fmt_title) if row.fmt_slug else None,
        categories=(
            [CategoryRef(id=row.cat_id, slug=row.cat_slug, name=row.cat_name, kind=row.cat_kind)]
            if row.cat_slug
            else []
        ),
        attendance=row.attendance,
        howto_verified_at=row.howto_verified_at,
        howto_unverified=row.state == "archived"
        and row.howto_verified_at is None
        and row.has_howto,
        has_howto=row.has_howto,
        foreign=not row.own,
        shared_documents=row.shared_docs,
        checklist_items=row.checklist_n,
    )


async def list_templates(
    session: AsyncSession,
    principal: Principal,
    q: str,
    filters: Filters,
    *,
    limit: int,
    offset: int,
) -> tuple[list[TemplateCard], int]:
    """Return one page of template cards and the total, by relevance, freshness and date."""
    words = parse(q) if q.strip() else []
    if q.strip() and not words:
        return [], 0
    reader = await reader_of(session, principal)
    statements = query.build("events", reader, filters, words, limit, offset, order="template")
    total = await session.scalar(statements.total) or 0
    rows = (await session.execute(statements.page)).all()
    return [card_of(row) for row in rows], total
