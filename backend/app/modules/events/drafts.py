"""Autosave drafts (E21): one row per person and dossier, never a revision.

A draft holds the unsaved fields of one person. It changes nothing about the dossier: no
`rev`, no `public_seq`, no cache rebuild, no audit entry. `PUT` checks the same rules as
`PATCH` (a locked field is a 409), so no one parks a critical change in `live`. Only a
successful `PATCH` makes the content effective and deletes the row. Nobody else reads a
draft, not even the admin.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import CursorResult, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.events.access import load_visible
from app.modules.events.models import EditorDraft
from app.modules.events.schemas import DraftFields
from app.modules.events.service import EventService
from app.shared.timeutil import utcnow

DRAFT_RETENTION = timedelta(days=14)
_JSON = TypeAdapter(dict[str, Any])


async def put_draft(
    session: AsyncSession,
    service: EventService,
    principal: Principal,
    event_id: UUID,
    fields: DraftFields,
    expected_rev: int,
) -> EditorDraft:
    """Store or overwrite the caller's draft (no commit).

    Raises:
        NotFoundError, ForbiddenError, VersionConflict, ConflictError: as `PATCH` would.
    """
    event, *_ = await service.check_edit(
        principal, event_id, expected_rev, EventService.changes_of(fields)
    )
    payload = _JSON.validate_python(
        fields.model_dump(by_alias=True, mode="json", exclude_unset=True)
    )
    statement = insert(EditorDraft).values(
        owner_kind="event",
        owner_id=event.id,
        principal_sub=principal.sub,
        base_rev=expected_rev,
        fields=payload,
        updated_at=utcnow(),
    )
    row = await session.scalar(
        statement.on_conflict_do_update(
            index_elements=["owner_kind", "owner_id", "principal_sub"],
            set_={
                "base_rev": statement.excluded.base_rev,
                "fields": statement.excluded.fields,
                "updated_at": statement.excluded.updated_at,
            },
        ).returning(EditorDraft)
    )
    assert row is not None
    return row


async def get_draft(
    session: AsyncSession, principal: Principal, event_id: UUID
) -> EditorDraft | None:
    """Return the caller's own draft, or `None` (404 for an unreadable dossier)."""
    event = await load_visible(session, principal, event_id)
    return await session.scalar(
        select(EditorDraft).where(
            EditorDraft.owner_kind == "event",
            EditorDraft.owner_id == event.id,
            EditorDraft.principal_sub == principal.sub,
        )
    )


async def delete_draft(session: AsyncSession, principal: Principal, event_id: UUID) -> None:
    """Discard the caller's own draft (no commit)."""
    event = await load_visible(session, principal, event_id)
    await session.execute(
        delete(EditorDraft).where(
            EditorDraft.owner_kind == "event",
            EditorDraft.owner_id == event.id,
            EditorDraft.principal_sub == principal.sub,
        )
    )


async def purge_older_than(session: AsyncSession, now: datetime) -> int:
    """Delete drafts idle for more than 14 days; return the count (no commit)."""
    result = await session.execute(
        delete(EditorDraft).where(EditorDraft.updated_at < now - DRAFT_RETENTION)
    )
    return cast(CursorResult[Any], result).rowcount or 0
