"""The sitemap and robots.txt (contract 2.8).

The sitemap lists the fixed pages, every active category and every public event that ended
within the last twelve months, at most 45 000 URLs (the protocol allows 50 000). The worker
stores the bytes as the snapshot `sitemap`; without one the route builds them live from the
view. `lastmod` is the last change of the event in UTC.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from xml.etree import ElementTree as ET

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("app.public")

MAX_URLS = 45_000
WINDOW = timedelta(days=366)
FIXED_PATHS = ("/", "/suche", "/kalender", "/abos", "/rueckblick")
NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
SNAPSHOT = "sitemap"
SITEMAP_TYPE = "application/xml; charset=utf-8"


def build(
    base_url: str,
    events: list[tuple[str, datetime]],
    categories: list[str],
    limit: int = MAX_URLS,
) -> bytes:
    """Return the sitemap bytes; `events` are `(slug, updated_at)`, newest start first."""
    base = base_url.rstrip("/")
    fixed = len(FIXED_PATHS) + len(categories)
    room = max(0, limit - fixed)
    if len(events) > room:
        logger.warning("snapshot_too_large sitemap events>%s", room)
    root = ET.Element("urlset", xmlns=NAMESPACE)
    for path in (*FIXED_PATHS, *(f"/k/{slug}" for slug in sorted(categories))):
        ET.SubElement(ET.SubElement(root, "url"), "loc").text = base + path
    for slug, updated in sorted(events[:room]):
        url = ET.SubElement(root, "url")
        ET.SubElement(url, "loc").text = f"{base}/e/{slug}"
        ET.SubElement(url, "lastmod").text = updated.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


async def read(
    session: AsyncSession, now: datetime, limit: int = MAX_URLS
) -> tuple[list[tuple[str, datetime]], list[str]]:
    """Read the window's events (newest first, one more than fits) and the active categories."""
    found = await session.execute(
        text(
            "SELECT slug, updated_at FROM public_event_v WHERE ends_at >= :since"
            f" ORDER BY starts_at DESC LIMIT {limit + 1}"
        ),
        {"since": now - WINDOW},
    )
    slugs = await session.execute(text("SELECT slug FROM public_category_v WHERE active"))
    return [(r.slug, r.updated_at) for r in found.all()], [r.slug for r in slugs.all()]


def robots(base_url: str) -> bytes:
    """Return `robots.txt`: pages and preview images stay open, the API and the app paths stay out."""
    lines = (
        "User-agent: *",
        "Allow: /e/",
        "Allow: /k/",
        "Allow: /suche",
        "Allow: /api/public/media/",
        "Disallow: /api/",
        "Disallow: /ics/",
        "Disallow: /dossiers",
        "Disallow: /verwaltung",
        "Disallow: /konto",
        "Disallow: /login",
        f"Sitemap: {base_url.rstrip('/')}/sitemap.xml",
    )
    return ("\n".join(lines) + "\n").encode()
