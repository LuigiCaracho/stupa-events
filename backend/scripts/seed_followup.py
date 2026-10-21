"""The documentation part of the dev seed: format, outcome, retrospective, howto and the past.

An archived dev dossier carries a retrospective, an outcome and a verified howto. This module
adds them through the real services, so the seed stays a user of the API's rules. Archived
editions move into the past with one `UPDATE` at the end, because a dossier can only be
created in the future.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.dossier import documents
from app.modules.dossier.schemas_documents import DocumentCreate
from app.modules.events.models import Event
from app.modules.followup import howto, outcome
from app.modules.followup.schemas import OutcomeIn
from app.modules.formats import service as formats
from app.modules.formats.howto import create_master
from app.shared.timeutil import utcnow


async def put_format(
    session: AsyncSession, principal: Principal, event: Event, definition: dict[str, Any]
) -> None:
    """Put the dossier into the format named in the definition (nothing without one)."""
    slug = definition.get("format")
    if slug:
        updated = await formats.set_event_format(session, principal, event.id, slug, event.rev)
        event.rev, event.format_id = updated.rev, updated.format_id


async def fill_followup(
    session: AsyncSession, principal: Principal, event: Event, definition: dict[str, Any]
) -> None:
    """Write the retrospective, the outcome and the howto, and verify the howto."""
    if not definition.get("retrospective"):
        return
    await documents.create(
        session,
        principal,
        event.id,
        DocumentCreate(kind="retrospective", body_md=definition["retrospective"]),
    )
    if definition.get("howto"):
        await documents.create(
            session,
            principal,
            event.id,
            DocumentCreate(kind="howto", title="Anleitung", body_md=definition["howto"]),
        )
        await howto.verify(session, principal, event.id)
    fresh = await session.get(Event, event.id)
    assert fresh is not None
    body = OutcomeIn.model_validate(definition["outcome"])
    await outcome.put_outcome(session, principal, event.id, body, fresh.rev)


async def move_into_the_past(session: AsyncSession, event: Event, days_ago: int) -> None:
    """Shift an archived dossier so that it started `days_ago` days ago (dev data only)."""
    shift = event.starts_at - (utcnow() - timedelta(days=days_ago))
    await session.execute(
        text(
            "UPDATE event SET starts_at = starts_at - CAST(:s AS interval),"
            " ends_at = ends_at - CAST(:s AS interval) WHERE id = :i"
        ),
        {"s": shift, "i": event.id},
    )


async def master_howto(session: AsyncSession, principal: Principal, slug: str) -> None:
    """Give the format a master howto copied from its oldest edition that has one."""
    fmt = await formats.load_format(session, slug)
    if fmt.master_howto_document_id is not None:
        return
    source = await session.scalar(
        text(
            "SELECT e.id FROM event e JOIN document d ON d.event_id = e.id AND d.kind = 'howto' "
            "WHERE e.format_id = :f ORDER BY e.starts_at LIMIT 1"
        ).bindparams(f=fmt.id)
    )
    if source is not None:
        await create_master(session, principal, fmt, source)
