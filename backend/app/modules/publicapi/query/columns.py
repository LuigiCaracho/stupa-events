"""Column lists for the raw SQL of the site queries (names only, never user input).

`CARD` is what a list card, a calendar entry and a facet need; it leaves out the long text and
the contact-like fields. `FULL` is every row column except the search vector (detail and ICS).
"""

from __future__ import annotations

from app.modules.publicapi.service import ROW_COLUMNS

LEFT_OUT = frozenset(
    {
        "description_md",
        "ticket_url",
        "website_url",
        "cost_text",
        "venue_address",
        "venue_city",
        "venue_text",
        "format_slug",
        "format_title",
        "organization_id",
        "hero_credit",
        "public_seq",
        "updated_at",
    }
)
FULL = ", ".join(c.key for c in ROW_COLUMNS)
CARD = ", ".join(c.key for c in ROW_COLUMNS if c.key not in LEFT_OUT)
