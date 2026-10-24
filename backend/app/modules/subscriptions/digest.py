"""Weekly digest: one Listmonk campaign draft per list, never sent by the job (E17).

For the Berlin week that starts on Monday, each list with at least one public event and at least
one subscriber gets a draft named `events-digest-<week>-<key>`. A category list shows the events
of the category and of its child categories; `_all` shows every event. The campaign is looked up by
name before it is created, so a crash between the Listmonk call and the DB write cannot create it
twice, and a second run changes nothing (`digest_run` is unique per week and list). Release is a
separate step (`digest_release.py`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Date, DateTime, Text, column, select, table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.subscriptions.digest_template import SUBJECT, DigestEvent, render_digest
from app.modules.subscriptions.listmonk_port import CampaignDraft, ListmonkPort
from app.modules.subscriptions.listmonk_sync import ALL_KEY
from app.modules.subscriptions.models import DigestRun, ListmonkList
from app.shared.timeutil import DEFAULT_TZID, utcnow

logger = logging.getLogger("app.subscriptions.digest")

Maker = async_sessionmaker[AsyncSession]

_EVENT = table(
    "public_event_v",
    column("slug", Text),
    column("title", Text),
    column("starts_at", DateTime(timezone=True)),
    column("all_day", Boolean),
    column("venue_name", Text),
    column("category_slug", Text),
    column("category_name", Text),
    column("category_parent_slug", Text),
    column("public_status", Text),
    column("starts_on", Date),
    column("ends_on", Date),
)


@dataclass(frozen=True, slots=True)
class WeekEvent:
    """An event of the week with the categories it counts for."""

    event: DigestEvent
    categories: frozenset[str]


def week_start_of(now: datetime) -> date:
    """Return the Monday of the Berlin week that contains `now`."""
    today = now.astimezone(ZoneInfo(DEFAULT_TZID)).date()
    return today - timedelta(days=today.weekday())


async def week_events(maker: Maker, week_start: date) -> list[WeekEvent]:
    """Read the scheduled public events that touch the week, sorted by start."""
    last = week_start + timedelta(days=6)
    stmt = (
        select(_EVENT)
        .where(
            _EVENT.c.public_status == "scheduled",
            _EVENT.c.starts_on <= last,
            _EVENT.c.ends_on >= week_start,
        )
        .order_by(_EVENT.c.starts_at, _EVENT.c.slug)
    )
    async with maker() as session:
        rows = (await session.execute(stmt)).all()
    return [
        WeekEvent(
            DigestEvent(r.slug, r.title, r.starts_at, r.all_day, r.venue_name, r.category_name),
            frozenset(s for s in (r.category_slug, r.category_parent_slug) if s),
        )
        for r in rows
    ]


def events_for(key: str, events: list[WeekEvent]) -> list[DigestEvent]:
    """Pick the events a list shows."""
    return [w.event for w in events if key == ALL_KEY or key in w.categories]


def campaign_name(week_start: date, key: str) -> str:
    """Return the unique campaign name of a week and list."""
    return f"events-digest-{week_start.isoformat()}-{key}"


async def _record(maker: Maker, week_start: date, key: str, **values: object) -> None:
    stmt = insert(DigestRun).values(week_start=week_start, list_key=key, **values)
    async with maker.begin() as session:
        await session.execute(stmt.on_conflict_do_nothing(constraint="uq_digest_run_week_start"))


async def build_drafts(
    maker: Maker, port: ListmonkPort, *, base_url: str, now: datetime | None = None
) -> dict[str, int]:
    """Create the digest drafts of the current week; return counters (`drafts`, `skipped`)."""
    week_start = week_start_of(now or utcnow())
    events = await week_events(maker, week_start)
    async with maker() as session:
        lists = [r[0] for r in (await session.execute(select(ListmonkList))).all()]
        known = set(
            (
                await session.scalars(
                    select(DigestRun.list_key).where(DigestRun.week_start == week_start)
                )
            ).all()
        )
    counters = {"drafts": 0, "skipped": 0}
    for row in sorted(lists, key=lambda r: r.key):
        shown = events_for(row.key, events)
        if row.archived_at is not None or row.key in known or not shown:
            continue
        if await port.subscriber_count(row.listmonk_id) == 0:
            await _record(maker, week_start, row.key, status="skipped", event_count=len(shown))
            counters["skipped"] += 1
            continue
        name = campaign_name(week_start, row.key)
        campaign_id = await port.find_campaign(name)
        if campaign_id is None:
            body = render_digest(shown, base_url=base_url, week_start=week_start)
            draft = CampaignDraft(name, SUBJECT, (row.listmonk_id,), body)
            campaign_id = await port.create_campaign(draft)
        await _record(
            maker,
            week_start,
            row.key,
            status="draft",
            event_count=len(shown),
            campaign_id=campaign_id,
        )
        counters["drafts"] += 1
    logger.info(
        "digest week=%s drafts=%s skipped=%s", week_start, counters["drafts"], counters["skipped"]
    )
    return counters
