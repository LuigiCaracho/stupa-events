"""The internal calendar (`GET /events?view=calendar`): dossiers that overlap a range of days.

`from` and `to` are local days, both inclusive, at most 100 days apart. A dossier is chosen
by overlap (`ends_at >= first midnight` and `starts_at < midnight after the last day`) among
the dossiers the caller reads. At most 500 entries;
colors are token names, never hex values.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.auth.schemas import CamelModel
from app.modules.events.access import visible_events_query
from app.modules.events.hints_data import howto_presence
from app.modules.events.listing import Filters, apply_filters, local_start
from app.modules.events.models import Event
from app.modules.orgs.models import Organization
from app.modules.taxonomy.models import Category, Venue
from app.shared.errors import FieldError, ValidationProblem

MAX_DAYS = 100
MAX_ENTRIES = 500


class CalendarOrg(CamelModel):
    """The organization of an entry with its color token."""

    slug: str
    short: str
    color_token: str | None


class CalendarCategory(CamelModel):
    """The main category of an entry with its color token."""

    slug: str
    color_token: str | None


class CalendarEntry(CamelModel):
    """One dossier in the grid: times, state and the tokens that color it."""

    id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    starts_on: date | None
    ends_on: date | None
    state: str
    public_status: Literal["scheduled", "cancelled", "postponed"]
    organization: CalendarOrg | None
    category: CalendarCategory | None
    venue_name: str | None
    howto_unverified: bool


class CalendarOut(CamelModel):
    """The entries of the range, newest-first never: ordered by start."""

    from_: date = Field(alias="from")
    to: date
    entries: list[CalendarEntry]
    truncated: bool


def check_range(start: date | None, end: date | None) -> tuple[date, date]:
    """Require both days and a range of at most 100 days.

    Raises:
        ValidationProblem: `range_required`, `range_invalid` or `range_too_large`.
    """
    if start is None or end is None:
        raise ValidationProblem(
            "from and to are required.",
            code="range_required",
            errors=[FieldError(field="from", msg="required")],
        )
    if end < start:
        raise ValidationProblem(
            "to must not be before from.",
            code="range_invalid",
            errors=[FieldError(field="to", msg="before from")],
        )
    if (end - start).days + 1 > MAX_DAYS:
        raise ValidationProblem(
            "The range may cover at most 100 days.",
            code="range_too_large",
            errors=[FieldError(field="to", msg="too large")],
        )
    return start, end


def _venue_name(event: Event, venue: Venue | None) -> str | None:
    if venue is None:
        return event.venue_text
    return None if venue.is_private else venue.name


async def calendar(
    session: AsyncSession,
    principal: Principal,
    filters: Filters,
    start: date,
    end: date,
) -> CalendarOut:
    """Select the readable dossiers that overlap `start` to `end` and shape the entries."""
    query = apply_filters(await visible_events_query(session, principal), filters, principal)
    query = query.where(
        Event.ends_at >= local_start(start), Event.starts_at < local_start(end + timedelta(days=1))
    )
    rows = list(
        await session.scalars(query.order_by(Event.starts_at, Event.id).limit(MAX_ENTRIES + 1))
    )
    truncated, events = len(rows) > MAX_ENTRIES, rows[:MAX_ENTRIES]
    orgs = await _by_id(session, Organization, {e.organization_id for e in events})
    categories = await _by_id(session, Category, {e.primary_category_id for e in events})
    venues = await _by_id(session, Venue, {e.venue_id for e in events})
    howtos = await howto_presence(session, events)
    entries = [
        CalendarEntry(
            id=e.id,
            title=e.title,
            starts_at=e.starts_at,
            ends_at=e.ends_at,
            all_day=e.all_day,
            starts_on=e.starts_on,
            ends_on=e.ends_on,
            state=e.state,
            public_status=e.public_status,  # type: ignore[arg-type]
            organization=_org(orgs.get(e.organization_id)),
            category=_category(categories.get(e.primary_category_id), orgs.get(e.organization_id)),
            venue_name=_venue_name(e, venues.get(e.venue_id)),
            howto_unverified=e.state == "archived"
            and e.howto_verified_at is None
            and e.id in howtos,
        )
        for e in events
    ]
    return CalendarOut.model_validate(
        {"from": start, "to": end, "entries": entries, "truncated": truncated}
    )


def _org(org: Organization | None) -> CalendarOrg | None:
    return (
        None
        if org is None
        else CalendarOrg(slug=org.slug, short=org.short, color_token=org.color_token)
    )


def _category(category: Category | None, org: Organization | None) -> CalendarCategory | None:
    if category is None:
        return None
    return CalendarCategory(
        slug=category.slug, color_token=category.color_token or (org.color_token if org else None)
    )


async def _by_id[T](session: AsyncSession, model: type[T], ids: set) -> dict:
    ids.discard(None)
    if not ids:
        return {}
    rows = await session.scalars(select(model).where(model.id.in_(ids)))  # type: ignore[attr-defined]
    return {row.id: row for row in rows}  # type: ignore[attr-defined]
