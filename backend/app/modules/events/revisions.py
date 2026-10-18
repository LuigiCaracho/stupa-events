"""Append-only history of a dossier: the revision snapshot, the status event and the audit."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.events.models import Event, EventRevision, EventStatusEvent

_SNAPSHOT_FIELDS = (
    "id",
    "slug",
    "state",
    "public_status",
    "title",
    "summary",
    "description_md",
    "starts_at",
    "ends_at",
    "tzid",
    "all_day",
    "organization_id",
    "venue_text",
    "primary_category_id",
    "hero_attachment_id",
    "image_exception",
    "origin_kind",
    "rev",
    "public_seq",
    "created_by",
    "submitted_by",
    "approved_by",
    "venue_id",
    "ticket_url",
    "website_url",
    "cost_text",
    "publish_at",
    "public_reason_code",
    "public_reason_text",
    "end_estimated",
    "flyer_checked_at",
    "text_reviewed_rev",
    "published_rev",
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def revision_payload(event: Event) -> dict[str, Any]:
    """Return the JSON snapshot of an event (ids and datetimes as strings)."""
    return {name: _jsonable(getattr(event, name)) for name in _SNAPSHOT_FIELDS}


async def append_revision(
    session: AsyncSession,
    event: Event,
    *,
    actor: str,
    field_class: str,
    note: str | None = None,
    actor_type: str = "human",
) -> None:
    """Write the revision row for the current `event.rev` (no commit)."""
    session.add(
        EventRevision(
            event_id=event.id,
            rev=event.rev,
            actor_id=actor,
            actor_type=actor_type,
            field_class=field_class,
            change_note=note,
            snapshot=revision_payload(event),
        )
    )
    await session.flush()


async def append_status(
    session: AsyncSession,
    event: Event,
    *,
    transition_id: str,
    from_state: str | None,
    actor: str,
    note: str | None = None,
    actor_type: str = "human",
    four_eyes: bool = False,
    submitted_by: str | None = None,
) -> None:
    """Write the status event for the current state of `event` (no commit)."""
    session.add(
        EventStatusEvent(
            event_id=event.id,
            from_state=from_state,
            to_state=event.state,
            transition_id=transition_id,
            actor_id=actor,
            actor_type=actor_type,
            note=note,
            four_eyes=four_eyes,
            submitted_by=submitted_by,
        )
    )
    await session.flush()


async def audit(
    session: AsyncSession,
    event: Event,
    *,
    actor: str,
    action: AuditAction,
    data: dict[str, Any] | None = None,
) -> None:
    """Write the audit entry of a mutation: ids and metadata only, never free text."""
    await audit_record(
        session,
        actor=actor,
        action=action,
        target_type="event",
        target_id=str(event.id),
        data={"rev": event.rev, **(data or {})},
    )
