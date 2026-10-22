"""schema.org `Event` as JSON-LD for the detail page (contract 2.8).

Only public fields go in. The block is a data island inside `<script type="application/ld+json">`
and is escaped so that no text can close the tag or break the line.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Row

from app.modules.publicapi.clock import BERLIN
from app.modules.publicapi.query.cards import image_set
from app.modules.publicapi.service import PRIVATE_VENUE

STATUS = {
    "scheduled": "https://schema.org/EventScheduled",
    "cancelled": "https://schema.org/EventCancelled",
    "postponed": "https://schema.org/EventPostponed",
}
_ESCAPES = {
    "<": "\\u003c",
    ">": "\\u003e",
    "&": "\\u0026",
    " ": "\\u2028",
    " ": "\\u2029",
}


def _place(row: Row[Any]) -> dict[str, Any] | None:
    if row.venue_name is None or row.venue_name == PRIVATE_VENUE:
        return None
    place: dict[str, Any] = {"@type": "Place", "name": row.venue_name}
    address = {
        key: value
        for key, value in (
            ("streetAddress", row.venue_address),
            ("addressLocality", row.venue_city),
        )
        if value
    }
    if address:
        place["address"] = {"@type": "PostalAddress", **address}
    return place


def event_data(row: Row[Any], base_url: str) -> dict[str, Any]:
    """Build the JSON-LD object of one event row."""
    if row.all_day and row.starts_on and row.ends_on:
        start, end = row.starts_on.isoformat(), row.ends_on.isoformat()
    else:
        start = row.starts_at.astimezone(BERLIN).isoformat()
        end = row.ends_at.astimezone(BERLIN).isoformat()
    images = image_set(row)
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": row.title,
        "startDate": start,
        "endDate": end,
        "eventStatus": STATUS[row.public_status],
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "organizer": {"@type": "Organization", "name": row.organization_name},
        "inLanguage": "de",
        "url": f"{base_url}/e/{row.slug}",
    }
    place = _place(row)
    if place:
        data["location"] = place
    if images:
        data["image"] = [f"{base_url}{images.og.url}"]
    if row.summary:
        data["description"] = row.summary
    if row.ticket_url:
        data["offers"] = {"@type": "Offer", "url": row.ticket_url}
    return data


def serialize(data: dict[str, Any]) -> str:
    """Serialize and escape for the inside of a script element."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    for char, escaped in _ESCAPES.items():
        text = text.replace(char, escaped)
    return text
