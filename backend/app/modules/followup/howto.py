"""Verify the howto of a dossier: the mark that releases T09 and dates the format.

`verify` sets `event.howto_verified_at/_by` and the `verified_at/_by` of the dossier howto.
After the end it is allowed in `live`, in `followup` and in `archived` (it changes no
content, only the mark); in `archived` it also dates the format, because no T09 will.
`unverify` takes the mark away until the dossier is archived. T09 itself dates the format
in `PipelineService` (contract 3.2).
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
from app.modules.events.writer import update_event
from app.modules.formats.verification import verify_format
from app.shared.errors import ConflictError
from app.shared.timeutil import utcnow

VERIFY_STATES = frozenset({"live", "followup", "archived"})


def _phase(event: Event, now: datetime) -> None:
    ended = event.state != "live" or event.ends_at <= now
    if event.state not in VERIFY_STATES or not ended:
        raise ConflictError("The action is not defined in this state.", code="invalid_transition")


async def _write(
    session: AsyncSession, principal: Principal, event: Event, values: dict[str, object]
) -> Event:
    updated = await update_event(session, event, values, states=[event.state])
    await revisions.append_revision(session, updated, actor=principal.sub, field_class="dossier")
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
    ensure_permission(principal, event, "event.submit", own_only=False)
    _phase(event, moment)
    if event.howto_verified_at is not None:
        return event
    await session.execute(
        update(Document)
        .where(Document.event_id == event.id, Document.kind == "howto")
        .values(verified_at=moment, verified_by=principal.sub)
    )
    if event.state == "archived":
        await verify_format(session, event, principal.sub, moment)
    return await _write(
        session, principal, event, {"howto_verified_at": moment, "howto_verified_by": principal.sub}
    )


async def unverify(
    session: AsyncSession, principal: Principal, event_id: UUID, *, now: datetime | None = None
) -> Event:
    """Take the mark away; refused once the dossier is archived."""
    event = await load_readable(session, principal, event_id)
    ensure_permission(principal, event, "event.submit", own_only=False)
    _phase(event, now or utcnow())
    if event.state == "archived":
        raise ConflictError("The dossier is archived.", code="dossier_closed")
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
