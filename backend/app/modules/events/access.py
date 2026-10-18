"""Read access to dossiers and the helpers that build a snapshot of one.

A principal reads the events of the organizations it has a role in; `event.read_all`
reads every event. A person also reads its own proposals (no organization, created by it).
An event the principal cannot read does not exist for it: 404, no existence oracle (PLAN 5.1).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.events.models import Event, EventStatusEvent
from app.modules.files.models import Attachment
from app.modules.orgs.scope import readable_org_ids
from app.modules.pipeline.snapshot import PosterSnapshot, Snapshot
from app.shared.errors import NotFoundError
from app.shared.timeutil import DEFAULT_TZID, to_local


async def load_visible(session: AsyncSession, principal: Principal, event_id: UUID) -> Event:
    """Load an event the principal may read.

    Raises:
        NotFoundError: The event does not exist or the principal may not read it.
    """
    scope = await readable_org_ids(session, principal)
    event = await session.get(Event, event_id)
    if event is None or not (
        scope is None
        or event.organization_id in scope
        or (event.organization_id is None and event.created_by == principal.sub)
    ):
        raise NotFoundError("event not found")
    return event


async def poster_of(session: AsyncSession, event: Event) -> Attachment | None:
    """Return the current poster attachment of the event, if any."""
    if event.hero_attachment_id is None:
        return None
    return await session.get(Attachment, event.hero_attachment_id)


def poster_snapshot(poster: Attachment | None) -> PosterSnapshot | None:
    """Reduce a poster row to the facts the guards read."""
    if poster is None or poster.retired_at is not None:
        return None
    return PosterSnapshot(
        scan_status=poster.scan_status,
        has_derivatives=bool(poster.derivatives),
        alt_text=poster.alt_text,
        credit=poster.credit,
        rights_basis=poster.rights_basis,
        persons_depicted=poster.persons_depicted,
        consent_note=poster.consent_note,
        created_at=poster.created_at,
    )


def valid_exception_reason(event: Event) -> str | None:
    """Return the reason of a valid image exception (at least 10 characters), else None."""
    reason = ((event.image_exception or {}).get("reason") or "").strip()
    return reason if len(reason) >= 10 else None


def snapshot_of(event: Event, poster: Attachment | None, **extra: object) -> Snapshot:
    """Build the snapshot of an event and its current poster.

    `extra` carries the values that need a query (`quarantined_attachments`,
    `entered_followup_at`, `open_proposals`); without them the guards see neutral values.
    """
    return Snapshot(
        state=event.state,
        title=event.title,
        summary=event.summary,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        organization_id=event.organization_id,
        primary_category_id=event.primary_category_id,
        venue_text=event.venue_text,
        created_by=event.created_by,
        submitted_by=event.submitted_by,
        poster=poster_snapshot(poster),
        image_exception_reason=valid_exception_reason(event),
        description_md=event.description_md,
        venue_id=event.venue_id,
        ticket_url=event.ticket_url,
        website_url=event.website_url,
        cost_text=event.cost_text,
        publish_at=event.publish_at,
        public_status=event.public_status,
        end_estimated=event.end_estimated,
        flyer_checked_at=event.flyer_checked_at,
        approved_by=event.approved_by,
        origin_kind=event.origin_kind,
        rev=event.rev,
        published_rev=event.published_rev,
        text_reviewed_rev=event.text_reviewed_rev,
        **extra,  # type: ignore[arg-type]
    )


async def guard_snapshot(
    session: AsyncSession,
    event: Event,
    poster: Attachment | None,
    *,
    starts_at: datetime | None = None,
) -> Snapshot:
    """Build the snapshot with everything the guards read, with three small queries.

    `starts_at` is a start that is about to replace the stored one, so the year of the
    poster check follows the new date.
    """
    conditions = [
        Attachment.event_id == event.id,
        Attachment.retired_at.is_(None),
        Attachment.scan_status != "clean",
    ]
    if event.hero_attachment_id is not None:
        conditions.append(Attachment.id != event.hero_attachment_id)
    quarantined = await session.scalar(
        select(func.count()).select_from(Attachment).where(*conditions)
    )
    entered = await session.scalar(
        select(func.max(EventStatusEvent.at)).where(
            EventStatusEvent.event_id == event.id, EventStatusEvent.to_state == "followup"
        )
    )
    snapshot = snapshot_of(
        event, poster, quarantined_attachments=quarantined or 0, entered_followup_at=entered
    )
    if snapshot.poster is None or poster is None:
        return snapshot
    reused = await _poster_reused_in_other_year(session, event, poster, starts_at)
    return replace(snapshot, poster=replace(snapshot.poster, reused_in_other_year=reused))


async def _poster_reused_in_other_year(
    session: AsyncSession, event: Event, poster: Attachment, starts_at: datetime | None
) -> bool:
    year = to_local(starts_at or event.starts_at, event.tzid or DEFAULT_TZID).year
    other = await session.scalar(
        select(Attachment.id)
        .join(Event, Event.id == Attachment.event_id)
        .where(
            Attachment.sha256 == poster.sha256,
            Attachment.event_id != event.id,
            Attachment.retired_at.is_(None),
            func.extract("year", func.timezone(DEFAULT_TZID, Event.starts_at)) != year,
        )
        .limit(1)
    )
    return other is not None


async def visible_events_query(session: AsyncSession, principal: Principal) -> Select[Event]:
    """Return `select(Event)` limited in SQL to the organizations the principal reads."""
    scope = await readable_org_ids(session, principal)
    query = select(Event)
    if scope is None:
        return query
    own_proposal = and_(Event.organization_id.is_(None), Event.created_by == principal.sub)
    return query.where(or_(Event.organization_id.in_(scope), own_proposal))
