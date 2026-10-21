"""Build `EventCard` rows with batched lookups: references, people, guard inputs, next move."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.principal import Principal
from app.modules.events.board import PRIMARY_TRANSITION, moves_for
from app.modules.events.card_extras import CardExtras, load_card_extras
from app.modules.events.card_schemas import EventCard, PersonRef
from app.modules.events.models import Event
from app.modules.events.presenter import howto_unverified
from app.modules.files.models import Attachment
from app.modules.formats.models import Format
from app.modules.orgs.models import Organization
from app.modules.orgs.schemas import OrgRef
from app.modules.orgs.scope import bind
from app.modules.pipeline.actor import actor_of
from app.modules.pipeline.decision import allowed_transitions, decide
from app.modules.pipeline.reasons import blockers
from app.modules.pipeline.schemas import reason_out
from app.modules.pipeline.transitions import TRANSITIONS
from app.modules.taxonomy.models import Category, Venue
from app.modules.taxonomy.schemas import CategoryRef
from app.shared.timeutil import utcnow

MAX_BLOCKERS = 3


async def _by_id[T](session: AsyncSession, model: type[T], ids: set) -> dict:
    if not ids:
        return {}
    rows = await session.scalars(select(model).where(model.id.in_(ids)))  # type: ignore[attr-defined]
    return {row.id: row for row in rows}  # type: ignore[attr-defined]


async def _names(session: AsyncSession, subs: set[str]) -> dict[str, str | None]:
    rows = await session.execute(
        select(PrincipalRow.sub, PrincipalRow.display_name).where(PrincipalRow.sub.in_(subs))
    )
    return dict(rows.all()) if subs else {}


def _venue_label(event: Event, venue: Venue | None) -> str | None:
    if venue is None:
        return event.venue_text
    return None if venue.is_private else venue.name


async def present_cards(
    session: AsyncSession, principal: Principal, events: Sequence[Event]
) -> list[EventCard]:
    """Turn events into cards, reading references, posters and names once."""
    await bind(session, principal)
    orgs = await _by_id(
        session, Organization, {e.organization_id for e in events if e.organization_id}
    )
    categories = await _by_id(
        session, Category, {e.primary_category_id for e in events if e.primary_category_id}
    )
    venues = await _by_id(session, Venue, {e.venue_id for e in events if e.venue_id})
    posters = await _by_id(
        session, Attachment, {e.hero_attachment_id for e in events if e.hero_attachment_id}
    )
    formats = await _by_id(session, Format, {e.format_id for e in events if e.format_id})
    names = await _names(session, {e.created_by for e in events})
    extras = await load_card_extras(session, events)
    now = utcnow()
    return [
        _card(principal, e, orgs, categories, venues, posters, formats, names, extras, now)
        for e in events
    ]


def _card(
    principal: Principal,
    event: Event,
    orgs: dict,
    categories: dict,
    venues: dict,
    posters: dict,
    formats: dict,
    names: dict[str, str | None],
    extras: CardExtras,
    now,  # noqa: ANN001
) -> EventCard:
    poster = posters.get(event.hero_attachment_id)
    snapshot = extras.snapshot(event, poster)
    actor = actor_of(principal, event.organization_id)
    allowed = allowed_transitions(snapshot, actor)
    primary = PRIMARY_TRANSITION.get(event.state)
    next_transition = primary if primary in allowed else None
    found = []
    if next_transition is not None:
        verdict = decide(TRANSITIONS[next_transition], snapshot, actor, now)
        found = blockers(list(verdict.reasons))
    org, category = orgs.get(event.organization_id), categories.get(event.primary_category_id)
    return EventCard(
        id=event.id,
        title=event.title,
        state=event.state,
        public_status=event.public_status,  # type: ignore[arg-type]
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        tzid=event.tzid,
        organization=OrgRef.model_validate(org) if org else None,
        venue_label=_venue_label(event, venues.get(event.venue_id)),
        primary_category=CategoryRef.model_validate(category) if category else None,
        publish_at=event.publish_at,
        has_poster=poster is not None and poster.retired_at is None,
        created_by=PersonRef(sub=event.created_by, display_name=names.get(event.created_by)),
        rev=event.rev,
        allowed_transitions=allowed,  # type: ignore[arg-type]
        next_transition=next_transition,  # type: ignore[arg-type]
        blockers=[reason_out(r) for r in found[:MAX_BLOCKERS]],
        blocker_count=len(found),
        moves=moves_for(event.state, allowed),  # type: ignore[arg-type]
        all_day=event.all_day,
        format_slug=formats[event.format_id].slug if event.format_id in formats else None,
        howto_unverified=howto_unverified(event, extras.has_howto(event.id)),
    )
