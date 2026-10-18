"""Build the wire shape `EventOut` from event rows with batched lookups."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.dossier.schemas import attachment_out
from app.modules.events.access import snapshot_of
from app.modules.events.models import Event
from app.modules.events.schemas import EventOut, ImageExceptionOut, PublicReasonOut
from app.modules.files.models import Attachment
from app.modules.orgs.models import Organization
from app.modules.orgs.schemas import OrgRef
from app.modules.orgs.scope import bind
from app.modules.pipeline.actor import actor_of
from app.modules.pipeline.allowed import allowed_actions
from app.modules.pipeline.decision import allowed_transitions
from app.modules.pipeline.fieldclass import editable_fields, lock_reason
from app.modules.taxonomy.models import Category, Venue
from app.modules.taxonomy.schemas import CategoryRef, VenueRef


def _exception_out(raw: dict | None) -> ImageExceptionOut | None:
    if not raw:
        return None
    return ImageExceptionOut(
        granted_by=raw["granted_by"], reason=raw["reason"], at=datetime.fromisoformat(raw["at"])
    )


def _venue_ref(venue: Venue | None) -> VenueRef | None:
    if venue is None:
        return None
    ref = VenueRef.model_validate(venue)
    if venue.is_private:
        return ref.model_copy(update={"address": None, "postcode": None, "city": None})
    return ref


def _reason_out(event: Event) -> PublicReasonOut | None:
    if event.public_status == "scheduled":
        return None
    return PublicReasonOut(code=event.public_reason_code, text=event.public_reason_text)  # type: ignore[arg-type]


async def present(
    session: AsyncSession, principal: Principal, events: Sequence[Event]
) -> list[EventOut]:
    """Turn events into `EventOut`, reading organizations, categories and posters once."""
    await bind(session, principal)
    org_ids = {e.organization_id for e in events if e.organization_id}
    category_ids = {e.primary_category_id for e in events if e.primary_category_id}
    poster_ids = {e.hero_attachment_id for e in events if e.hero_attachment_id}
    venue_ids = {e.venue_id for e in events if e.venue_id}
    orgs = (
        {
            o.id: o
            for o in (
                await session.scalars(select(Organization).where(Organization.id.in_(org_ids)))
            )
        }
        if org_ids
        else {}
    )
    categories = (
        {
            c.id: c
            for c in (await session.scalars(select(Category).where(Category.id.in_(category_ids))))
        }
        if category_ids
        else {}
    )
    posters = (
        {
            a.id: a
            for a in (
                await session.scalars(select(Attachment).where(Attachment.id.in_(poster_ids)))
            )
        }
        if poster_ids
        else {}
    )
    venues = (
        {v.id: v for v in (await session.scalars(select(Venue).where(Venue.id.in_(venue_ids))))}
        if venue_ids
        else {}
    )
    return [_one(principal, e, orgs, categories, posters, venues) for e in events]


def _one(
    principal: Principal,
    event: Event,
    orgs: dict,
    categories: dict,
    posters: dict,
    venues: dict,
) -> EventOut:
    poster = posters.get(event.hero_attachment_id)
    org = orgs.get(event.organization_id)
    category = categories.get(event.primary_category_id)
    actor = actor_of(principal, event.organization_id)
    snapshot = snapshot_of(event, poster)
    venue = venues.get(event.venue_id)
    return EventOut(
        id=event.id,
        slug=event.slug,
        state=event.state,
        public_status=event.public_status,  # type: ignore[arg-type]
        title=event.title,
        summary=event.summary,
        description_md=event.description_md,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        tzid=event.tzid,
        all_day=event.all_day,
        organization=OrgRef.model_validate(org) if org else None,
        venue_id=event.venue_id,
        venue=_venue_ref(venue),
        venue_text=event.venue_text,
        cost_text=event.cost_text,
        ticket_url=event.ticket_url,
        website_url=event.website_url,
        publish_at=event.publish_at,
        public_reason=_reason_out(event),
        end_estimated=event.end_estimated,
        text_reviewed_rev=event.text_reviewed_rev,
        published_rev=event.published_rev,
        flyer_checked_at=event.flyer_checked_at,
        primary_category=CategoryRef.model_validate(category) if category else None,
        poster=attachment_out(poster) if poster else None,
        image_exception=_exception_out(event.image_exception),
        rev=event.rev,
        created_by=event.created_by,
        submitted_by=event.submitted_by,
        approved_by=event.approved_by,
        created_at=event.created_at,
        updated_at=event.updated_at,
        allowed_transitions=allowed_transitions(snapshot, actor),  # type: ignore[arg-type]
        allowed_actions=allowed_actions(snapshot, actor),  # type: ignore[arg-type]
        editable_fields=editable_fields(snapshot, actor),
        lock_reason=lock_reason(snapshot, actor),
    )
