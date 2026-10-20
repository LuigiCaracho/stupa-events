"""Event context and preview of user mail templates (service for the dossier module).

`render_preview` is the one entry point for `POST .../render-preview`: it builds the
catalog context from the dossier and renders the unsaved draft or the stored template.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.models import Event
from app.modules.notifications.placeholders import render_template
from app.modules.orgs.models import Organization
from app.modules.taxonomy.models import Venue
from app.shared.timeutil import DEFAULT_TZID

STARTS_LOCAL_FORMAT = "%d.%m.%Y, %H:%M Uhr"


async def event_context(session: AsyncSession, event: Event) -> dict[str, dict[str, str]]:
    """Build the render context of the catalog; a missing value is the empty string."""
    zone = ZoneInfo(event.tzid or DEFAULT_TZID)
    starts = event.starts_at.astimezone(zone)
    venue = event.venue_text or ""
    if event.venue_id is not None:
        venue = (
            await session.execute(select(Venue.name).where(Venue.id == event.venue_id))
        ).scalar_one_or_none() or venue
    org = ""
    if event.organization_id is not None:
        org = (
            await session.execute(
                select(Organization.name).where(Organization.id == event.organization_id)
            )
        ).scalar_one_or_none() or ""
    return {
        "event": {"title": event.title, "starts_local": starts.strftime(STARTS_LOCAL_FORMAT)},
        "venue": {"name": venue},
        "org": {"name": org},
    }


async def render_preview(
    session: AsyncSession, event: Event, subject: str, body: str
) -> tuple[str, str]:
    """Render a template (draft or stored) against the dossier.

    Raises:
        ValidationProblem: 422 `template_invalid` with `reasons[]` (`unknown_placeholder`
            carries `field` and `allowed`).
    """
    return render_template(subject, body, await event_context(session, event))
