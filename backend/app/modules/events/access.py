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
from app.modules.dossier.guard_data import GuardData, load_guard_data
from app.modules.events import facts
from app.modules.events.models import Event, EventStatusEvent
from app.modules.files.models import Attachment
from app.modules.orgs.scope import readable_org_ids
from app.modules.pipeline.snapshot import PosterSnapshot, Snapshot
from app.shared.errors import NotFoundError

WAIVER_MIN_CHARS = 10


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


def location_is_confirmed(event: Event) -> bool:
    """Tell if the venue of a dossier is settled: a venue row, no free text, or a confirmed one."""
    return (
        event.venue_id is not None
        or not (event.venue_text or "").strip()
        or (event.location_confirmed_at is not None and event.location_precision != "hidden")
    )


def outcome_is_set(event: Event) -> bool:
    """Tell if the outcome is complete: the waiver with a reason, or attendance and costs."""
    outcome = event.outcome or {}
    if outcome.get("waived"):
        return len((outcome.get("waivedReason") or "").strip()) >= WAIVER_MIN_CHARS
    return outcome.get("attendance") is not None and outcome.get("costsCents") is not None


def snapshot_of(event: Event, poster: Attachment | None, **extra: object) -> Snapshot:
    """Build the snapshot of an event and its current poster.

    `extra` carries the values that need a query (`quarantined_attachments`,
    `entered_followup_at`, `open_proposals`, the follow-up counts); without them the guards
    see neutral values. The location and the outcome come from the row itself.
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
        format_id=event.format_id,
        all_day=bool(event.all_day),
        starts_on=event.starts_on,
        ends_on=event.ends_on,
        location_confirmed=location_is_confirmed(event),
        outcome_set=outcome_is_set(event),
        **extra,  # type: ignore[arg-type]
    )


async def guard_snapshot(
    session: AsyncSession,
    event: Event,
    poster: Attachment | None,
    *,
    starts_at: datetime | None = None,
) -> Snapshot:
    """Build the snapshot with everything the guards read, with a few grouped queries.

    `starts_at` is a start that is about to replace the stored one, so the year of the
    poster check follows the new date.
    """
    data = (
        await load_guard_data(
            session, [event], starts_at={event.id: starts_at} if starts_at else None
        )
    )[event.id]
    entered = await session.scalar(
        select(func.max(EventStatusEvent.at)).where(
            EventStatusEvent.event_id == event.id, EventStatusEvent.to_state == "followup"
        )
    )
    return snapshot_with(event, poster, data, entered)


def snapshot_with(
    event: Event, poster: Attachment | None, data: GuardData, entered_followup_at: datetime | None
) -> Snapshot:
    """Build the full guard snapshot from the row, the poster and the M4 guard data."""
    snapshot = snapshot_of(
        event,
        poster,
        quarantined_attachments=data.quarantined_attachments,
        entered_followup_at=entered_followup_at,
        open_comments=data.open_comments,
        open_hero_comments=data.open_hero_comments,
        open_required_checklist=data.open_required_checklist,
        open_required_followup=data.open_required_followup,
        retrospective_filled=data.retrospective_filled,
        howto_verified=event.howto_verified_at is not None or not data.howto_present,
        facts_error=facts.error_for(data.required_profile, event.facts),
    )
    if snapshot.poster is None or not data.poster_reused:
        return snapshot
    return replace(snapshot, poster=replace(snapshot.poster, reused_in_other_year=True))


async def visible_events_query(session: AsyncSession, principal: Principal) -> Select[Event]:
    """Return `select(Event)` limited in SQL to the organizations the principal reads."""
    scope = await readable_org_ids(session, principal)
    query = select(Event)
    if scope is None:
        return query
    own_proposal = and_(Event.organization_id.is_(None), Event.created_by == principal.sub)
    return query.where(or_(Event.organization_id.in_(scope), own_proposal))
