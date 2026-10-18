"""Read side of the revision history: the list, the detail and the changed fields.

Change notes (returns, reasons) and the internal snapshot fields (image exception, the
people of the four-eyes chain) go only to callers with `event.edit` in the organization.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic.alias_generators import to_camel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.principal import Principal
from app.modules.auth.schemas import CamelModel
from app.modules.events.access import load_visible
from app.modules.events.card_schemas import PersonRef
from app.modules.events.models import EventRevision
from app.shared.errors import NotFoundError

IGNORED_KEYS = frozenset({"rev"})
INTERNAL_KEYS = frozenset({"image_exception", "created_by", "submitted_by", "approved_by"})


class RevisionOut(CamelModel):
    """One revision without its snapshot."""

    rev: int
    at: datetime
    actor: PersonRef
    actor_type: str
    field_class: str
    change_note: str | None
    changed_fields: list[str]


class RevisionDetail(RevisionOut):
    """A revision with its full snapshot (camelCase keys)."""

    snapshot: dict[str, Any]


def changed_fields(before: dict[str, Any] | None, after: dict[str, Any]) -> list[str]:
    """Name the snapshot fields (camelCase) that differ from the previous revision."""
    if before is None:
        return []
    keys = (set(before) | set(after)) - IGNORED_KEYS
    return sorted(to_camel(k) for k in keys if before.get(k) != after.get(k))


async def _names(session: AsyncSession, subs: set[str]) -> dict[str, str | None]:
    rows = await session.execute(
        select(PrincipalRow.sub, PrincipalRow.display_name).where(PrincipalRow.sub.in_(subs))
    )
    return dict(rows.all())


def _out(
    row: EventRevision,
    previous: EventRevision | None,
    names: dict[str, str | None],
    *,
    detail: bool,
    internal: bool,
) -> RevisionOut | RevisionDetail:
    common: dict[str, Any] = {
        "rev": row.rev,
        "at": row.at,
        "actor": PersonRef(sub=row.actor_id or "", display_name=names.get(row.actor_id or "")),
        "actor_type": row.actor_type,
        "field_class": row.field_class,
        "change_note": row.change_note if internal else None,
        "changed_fields": changed_fields(previous.snapshot if previous else None, row.snapshot),
    }
    if detail:
        shown = {
            to_camel(k): v for k, v in row.snapshot.items() if internal or k not in INTERNAL_KEYS
        }
        return RevisionDetail(**common, snapshot=shown)
    return RevisionOut(**common)


async def list_revisions(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    *,
    field_class: str | None,
    limit: int,
    offset: int,
    min_rev: int = 0,
) -> tuple[list[RevisionOut], int]:
    """Return a page of revisions, newest first, with the total."""
    event = await load_visible(session, principal, event_id)
    query = select(EventRevision).where(EventRevision.event_id == event.id)
    if field_class:
        query = query.where(EventRevision.field_class == field_class)
    if min_rev:
        query = query.where(EventRevision.rev > min_rev)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        await session.scalars(query.order_by(EventRevision.rev.desc()).limit(limit).offset(offset))
    )
    previous = {
        r.rev: r
        for r in await session.scalars(
            select(EventRevision).where(
                EventRevision.event_id == event.id,
                EventRevision.rev.in_({r.rev - 1 for r in rows}),
            )
        )
    }
    internal = principal.has("event.edit", event.organization_id)
    names = await _names(session, {r.actor_id for r in rows if r.actor_id})
    return [
        _out(r, previous.get(r.rev - 1), names, detail=False, internal=internal) for r in rows
    ], total  # type: ignore[misc]


async def revision_detail(
    session: AsyncSession, principal: Principal, event_id: UUID, rev: int
) -> RevisionDetail:
    """Return one revision with its snapshot.

    Raises:
        NotFoundError: The dossier is unreadable or has no such revision.
    """
    event = await load_visible(session, principal, event_id)
    rows = list(
        await session.scalars(
            select(EventRevision).where(
                EventRevision.event_id == event.id, EventRevision.rev.in_((rev - 1, rev))
            )
        )
    )
    by_rev = {r.rev: r for r in rows}
    if rev not in by_rev:
        raise NotFoundError("revision not found")
    row = by_rev[rev]
    internal = principal.has("event.edit", event.organization_id)
    names = await _names(session, {row.actor_id} if row.actor_id else set())
    return _out(row, by_rev.get(rev - 1), names, detail=True, internal=internal)  # type: ignore[return-value]
