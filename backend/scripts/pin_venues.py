"""One-off pinning of the archive venues (`python -m scripts.pin_venues`).

Default is a dry run: no network, no write, only the plan. `--apply` writes the pins that need
no network (venues of a drawn campus building get the polygon's centroid, source `import`,
precision `building`). `--live` adds the Nominatim lookups (street and town, curated
destinations) at the policy's pace of one request per 2 seconds and needs `--contact`.
Private and inactive venues are never touched. The result lands as a Markdown table in the
file of `--report` (default `docs/VENUES-PINNED.md`). It uses `DATABASE_URL` and `REDIS_URL`
of the environment, so it never touches a live system by itself.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker
from app.modules.events.postcommit import FEED_VERSION_KEY
from app.modules.geocode import nominatim
from app.modules.geocode.service import resolve
from app.modules.taxonomy.models import CampusBuilding, Venue
from app.modules.taxonomy.pinning import Decision, plan, report
from app.settings import Settings, get_settings
from app.shared.errors import AppError, RateLimitedError
from app.shared.timeutil import utcnow

DEFAULT_REPORT = Path(__file__).resolve().parents[2] / "docs" / "VENUES-PINNED.md"
SLOT_WAIT = 2.1
Outcome = tuple[Decision, str, Decimal | None, Decimal | None]


def pin(venue: Venue, lat: Decimal, lon: Decimal, source: str, at: datetime) -> None:
    """Pin a venue; `hidden` becomes `building`, a precision chosen by a human stays."""
    venue.lat, venue.lon = lat, lon
    venue.geocode_source, venue.geocoded_at = source, at
    if venue.public_precision in (None, "hidden"):
        venue.public_precision = "building"


async def lookup(
    session: AsyncSession,
    redis: Any,
    settings: Settings,
    client: httpx.AsyncClient,
    decision: Decision,
) -> tuple[Decimal, Decimal] | None:
    """Ask for one query, waiting out the 2-second slot; `None` means nothing was found."""
    assert decision.query is not None
    while True:
        try:
            found = await resolve(session, redis, settings, decision.query, client)
        except RateLimitedError:
            await asyncio.sleep(SLOT_WAIT)
            continue
        return (found.lat, found.lon) if found.found and found.lat and found.lon else None


async def run_one(
    session: AsyncSession,
    redis: Any,
    client: httpx.AsyncClient | None,
    settings: Settings,
    decision: Decision,
    venue: Venue,
    *,
    apply: bool,
) -> Outcome:
    """Carry out one decision as far as the flags allow; return what happened."""
    if decision.action == "campus" and decision.lat and decision.lon:
        if apply:
            pin(venue, decision.lat, decision.lon, "import", utcnow())
        return decision, "gepinnt" if apply else "würde gepinnt", decision.lat, decision.lon
    if decision.needs_network:
        if not (apply and client is not None and redis is not None):
            return decision, "offen (nur mit --apply --live)", None, None
        try:
            hit = await lookup(session, redis, settings, client, decision)
        except AppError as exc:
            return decision, f"Fehler: {exc.code}", None, None
        if hit is None:
            return decision, "nicht gefunden, bleibt verborgen", None, None
        pin(venue, hit[0], hit[1], "nominatim", utcnow())
        return decision, "gepinnt", hit[0], hit[1]
    if decision.action == "pinned":
        return decision, "schon gepinnt", venue.lat, venue.lon
    return (
        decision,
        "bleibt verborgen" if decision.action == "hidden" else "unverändert",
        None,
        None,
    )


async def main(args: argparse.Namespace) -> int:
    """Plan, run and report; return the number of pinned venues."""
    settings = get_settings().model_copy(
        update={"nominatim_enabled": args.live, "nominatim_contact": args.contact}
    )
    redis = aioredis.from_url(settings.redis_url) if args.live else None
    client = nominatim.new_client() if args.live else None
    async with get_sessionmaker()() as session:
        venues = list(await session.scalars(select(Venue).order_by(Venue.name)))
        polygons = {b.number: b.geometry for b in await session.scalars(select(CampusBuilding))}
        by_slug = {v.slug: v for v in venues}
        outcomes = [
            await run_one(session, redis, client, settings, d, by_slug[d.slug], apply=args.apply)
            for d in plan(venues, polygons)
        ]
        if args.apply:
            await session.commit()
            if redis is not None:
                await redis.incr(FEED_VERSION_KEY)
    if client is not None and redis is not None:
        await client.aclose()
        await redis.aclose()
    table = report(outcomes)
    args.report.write_text(
        f"# Gepinnte Orte\n\nLauf vom {utcnow():%Y-%m-%d %H:%M} UTC, "
        f"Modus {'live' if args.live else 'apply' if args.apply else 'Trockenlauf'}. "
        "Koordinaten auf drei Dezimalen gerundet. `offen` heißt: braucht einen Nominatim-Lauf "
        "(`--apply --live --contact <Adresse>`, höchstens 15 Anfragen im Abstand von 2 s).\n\n"
        + table,
        encoding="utf-8",
    )
    print(table)
    return sum(1 for _, outcome, _, _ in outcomes if outcome == "gepinnt")


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write the pins")
    parser.add_argument("--live", action="store_true", help="allow Nominatim lookups")
    parser.add_argument("--contact", help="contact for the User-Agent (needed with --live)")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    if args.live and not (args.apply and args.contact):
        parser.error("--live needs --apply and --contact")
    return args


if __name__ == "__main__":
    print(f"pinned {asyncio.run(main(parse()))} venue(s)")
