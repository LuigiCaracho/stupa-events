"""View rows to the site shapes: card, detail and calendar entry, field by field.

No ORM object and no `model_dump` is involved; a row is public by construction because
`public_event_v` is the only source. Image and event URLs are root-relative.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Row

from app.modules.publicapi.schemas import PublicFormat, PublicStatusReason
from app.modules.publicapi.service import MEDIA_PATH, row_categories, row_venue
from app.modules.publicapi.site_schemas import (
    PublicCalendarEntry,
    PublicCardImage,
    PublicEventCard,
    PublicEventDetail,
    PublicImageSet,
    PublicImageVariant,
    PublicOrganizationRef,
)
from app.modules.publicapi.textsafe import text_html

THUMB, CARD, OG = "thumb_400", "card_1200", "og_1200x630"


def _variant(row: Row[Any], name: str) -> PublicImageVariant | None:
    derivative = (row.hero_derivatives or {}).get(name)
    if row.hero_sha is None or derivative is None:
        return None
    return PublicImageVariant(
        url=f"{MEDIA_PATH}/{derivative['id']}.webp",
        width=derivative["width"],
        height=derivative["height"],
    )


def card_image(row: Row[Any]) -> PublicCardImage | None:
    """The thumbnail of a card, or `None` for an event without a usable poster."""
    thumb = _variant(row, THUMB)
    if thumb is None:
        return None
    return PublicCardImage(
        url=thumb.url, width=thumb.width, height=thumb.height, alt=row.hero_alt or ""
    )


def image_set(row: Row[Any]) -> PublicImageSet | None:
    """The three poster sizes of a detail page, or `None` without all of them."""
    thumb, card, og = _variant(row, THUMB), _variant(row, CARD), _variant(row, OG)
    if thumb is None or card is None or og is None:
        return None
    return PublicImageSet(
        thumb=thumb, card=card, og=og, alt=row.hero_alt or "", credit=row.hero_credit or ""
    )


def _core(row: Row[Any]) -> dict[str, Any]:
    return {
        "slug": row.slug,
        "title": row.title,
        "summary": row.summary,
        "starts_at": row.starts_at.astimezone(UTC),
        "ends_at": row.ends_at.astimezone(UTC),
        "all_day": row.all_day,
        "starts_on": row.starts_on,
        "ends_on": row.ends_on,
        "tzid": row.tzid,
        "status": row.public_status,
        "status_reason": (
            None
            if row.public_status == "scheduled"
            else PublicStatusReason(code=row.public_reason_code, text=row.public_reason_text)
        ),
        "organization": PublicOrganizationRef(
            slug=row.organization_slug, name=row.organization_name, short=row.organization_short
        ),
        "venue_name": row.venue_name,
        "categories": row_categories(row),
        "path": f"/e/{row.slug}",
    }


def to_card(row: Row[Any]) -> PublicEventCard:
    """Build the list card of one view row."""
    return PublicEventCard(**_core(row), image=card_image(row))


def to_detail(row: Row[Any], now: datetime, more: list[PublicEventCard]) -> PublicEventDetail:
    """Build the detail page of one view row; `more` are later events of the same format."""
    return PublicEventDetail(
        **_core(row),
        image=image_set(row),
        description_html=text_html(row.description_md),
        venue=row_venue(row),
        venue_text=row.venue_text,
        ticket_url=row.ticket_url,
        website_url=row.website_url,
        cost_text=row.cost_text,
        format=PublicFormat(slug=row.format_slug, title=row.format_title)
        if row.format_slug
        else None,
        ics_url=f"/ics/e/{row.slug}.ics",
        is_past=row.ends_at < now,
        updated_at=row.updated_at.astimezone(UTC),
        sequence=row.public_seq,
        more=more,
    )


def to_entry(row: Row[Any]) -> PublicCalendarEntry:
    """Build the calendar entry of one view row."""
    return PublicCalendarEntry(
        slug=row.slug,
        title=row.title,
        starts_at=row.starts_at.astimezone(UTC),
        ends_at=row.ends_at.astimezone(UTC),
        all_day=row.all_day,
        starts_on=row.starts_on,
        ends_on=row.ends_on,
        status=row.public_status,
        category_slug=row.category_slug,
    )
