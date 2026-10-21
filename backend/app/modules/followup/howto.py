"""Verify the howto of a dossier: the "Anleitung geprüft" mark that dates the format.

`verify` sets `event.howto_verified_at/_by` and the `verified_at/_by` of the dossier howto.
It is allowed in `published` and `archived` for `event.publish` (it changes no content, only
the mark) and dates the format of the dossier when the caller may (`verify_format`).
`unverify` takes the mark away until the dossier is archived.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.dossier.models_documents import Document
from app.modules.dossier.rules import ensure_permission, load_readable
from app.modules.events import revisions
from app.modules.events.models import Event
from app.modules.events.states import EventState
from app.modules.events.writer import update_event
from app.modules.formats.verification import verify_format
from app.shared.errors import ConflictError
from app.shared.timeutil import utcnow

VERIFY_STATES = frozenset({EventState.PUBLISHED, EventState.ARCHIVED})


def _phase(event: Event) -> None:
    if event.state not in VERIFY_STATES:
        raise ConflictError("The action is not defined in this state.", code="invalid_state")


async def _write(
    session: AsyncSession, principal: Principal, event: Event, values: dict[str, object]
) -> Event:
    updated = await update_event(session, event, values, states=[event.state])
    await revisions.append_revision(session, updated, actor=principal.sub)
    await revisions.audit(
        session, updated, actor=principal.sub, action=AuditAction.EVENT_HOWTO_VERIFY, data={}
    )
    return updated


async def verify(
    session: AsyncSession, principal: Principal, event_id: UUID, *, now: datetime | None = None
) -> Event:
    """Mark the howto verified (idempotent: a second call changes nothing)."""
    moment = now or utcnow()
    event = await load_readable(session, principal, event_id)
    ensure_permission(principal, event, "event.publish", own_only=False)
    _phase(event)
    if event.howto_verified_at is not None:
        return event
    await session.execute(
        update(Document)
        .where(Document.event_id == event.id, Document.kind == "howto")
        .values(verified_at=moment, verified_by=principal.sub)
    )
    await verify_format(session, principal, event, moment)
    return await _write(
        session, principal, event, {"howto_verified_at": moment, "howto_verified_by": principal.sub}
    )


async def unverify(session: AsyncSession, principal: Principal, event_id: UUID) -> Event:
    """Take the mark away; refused once the dossier is archived."""
    event = await load_readable(session, principal, event_id)
    ensure_permission(principal, event, "event.publish", own_only=False)
    _phase(event)
    if event.state == EventState.ARCHIVED:
        raise ConflictError("The dossier is archived.", code="invalid_state")
    if event.howto_verified_at is None:
        return event
    await session.execute(
        update(Document)
        .where(Document.event_id == event.id, Document.kind == "howto")
        .values(verified_at=None, verified_by=None)
    )
    return await _write(
        session, principal, event, {"howto_verified_at": None, "howto_verified_by": None}
    )
