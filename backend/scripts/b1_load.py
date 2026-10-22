"""B1 load check: 5000 synthetic public events in a scratch database and the p95 of the site routes.

`seed_events` fills the scratch database by SQL (fixed seed, a fixed word list, the twelve events of
the search stock inside), `measure` sends N requests per route through the ASGI app without the
response cache (so every request reaches the view) and reports min, median, p95 and max in
milliseconds. `explain_search` returns the plan of the text search as the role `events_public` sees
it. Run `uv run python -m scripts.b1_load` to do all of it on a throwaway Postgres container, or
import the functions from `tests/integration/publicapi/test_public_perf.py`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import Engine, TextClause, text

from tests.integration.publicapi.search_stock import STOCK

LIMIT_MS = 300.0
WORDS = [
    "Movienight",
    "Karaoke",
    "Skiausfahrt",
    "Sitzung",
    "Workshop",
    "Konzert",
    "Party",
    "Festival",
    "Kochkurs",
    "Lesung",
    "Turnier",
    "Wanderung",
    "Stammtisch",
    "Spieleabend",
    "Vortrag",
    "Podium",
    "Exkursion",
    "Tanzabend",
    "Flohmarkt",
    "Campusfest",
    "Grillen",
    "Quiz",
    "Hackathon",
    "Löten",
    "Reparieren",
    "Yoga",
    "Fotowalk",
    "Theater",
    "Kino",
    "Pubquiz",
]
PLACES = [
    "Hörsaal",
    "Mensa",
    "Rappen",
    "Kinosaal",
    "Campus",
    "Werkstatt",
    "Foyer",
    "Garten",
    "Bibliothek",
]
MIN_REQUESTS = 200


@dataclass(frozen=True, slots=True)
class Stats:
    """Latency of one route in milliseconds."""

    name: str
    count: int
    median: float
    p95: float
    worst: float


def p95(samples: Sequence[float]) -> float:
    """Return the 95th percentile (nearest rank)."""
    ordered = sorted(samples)
    return ordered[max(0, -(-95 * len(ordered) // 100) - 1)]


def seed_events(engine: Engine, count: int = 5000, seed: int = 20261022) -> list[str]:
    """Insert `count` published events plus the search stock; return a sample of slugs.

    Titles and summaries come from a word list, starts spread over -200 to +300 days.
    """
    rng = random.Random(seed)
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    with engine.begin() as conn:
        orgs = list(conn.execute(text("SELECT id FROM organization ORDER BY slug")).scalars())
        cats = list(
            conn.execute(text("SELECT id FROM category WHERE active ORDER BY slug")).scalars()
        )
        rows: list[dict[str, Any]] = []
        titles = [(title, summary) for _, title, summary, *_ in STOCK]
        for index in range(count):
            first, second = rng.sample(WORDS, 2)
            title = titles[index][0] if index < len(titles) else f"{first} {second} {index}"
            summary = (
                titles[index][1]
                if index < len(titles)
                else f"{rng.choice(WORDS)} im {rng.choice(PLACES)}"
            )
            days = index + 1 if index < len(titles) else rng.randint(-200, 300)
            start = now + timedelta(days=days, hours=rng.randint(0, 23))
            rows.append(
                {
                    "title": title,
                    "summary": summary,
                    "description": " ".join(rng.choices(WORDS, k=30)),
                    "start": start,
                    "end": start + timedelta(hours=rng.randint(1, 5)),
                    "org": rng.choice(orgs),
                    "cat": rng.choice(cats),
                    "slug": f"{start:%Y-%m-%d}-b1-{index}",
                    "place": rng.choice(PLACES),
                }
            )
        conn.execute(
            text(
                "INSERT INTO event (title, summary, description_md, starts_at, ends_at, "
                "organization_id, primary_category_id, created_by, state, slug, tzid, "
                "published_at, venue_text, location_precision) VALUES (:title, :summary, "
                ":description, :start, :end, :org, :cat, 'b1-load', 'published', :slug, "
                "'Europe/Berlin', now(), :place, 'building')"
            ),
            rows,
        )
        conn.execute(text("ANALYZE event"))
    return [r["slug"] for r in rows[:: max(1, count // 50)]]


async def measure(
    client: AsyncClient, name: str, requests: Callable[[int], tuple[str, dict[str, Any]]], n: int
) -> Stats:
    """Send `n` GET requests and time each; every answer must be a 200."""
    samples: list[float] = []
    for i in range(n):
        path, params = requests(i)
        began = time.perf_counter()
        response = await client.get(path, params=params)
        samples.append((time.perf_counter() - began) * 1000)
        assert response.status_code == 200, (name, path, params, response.text[:200])
    return Stats(name, n, statistics.median(samples), p95(samples), max(samples))


def routes(slugs: Sequence[str]) -> dict[str, Callable[[int], tuple[str, dict[str, Any]]]]:
    """The measured routes, each a function of the request index."""
    queries = ("Kino", "Movie", "Movienigth", "Karaokke", "Sitzung", "Ski", "Party Hörsaal", "2026")
    categories = ("kino", "party", "workshop", "fachschaft")
    month = datetime.now(UTC)
    return {
        "list": lambda i: ("/api/public/events", {"limit": 20 + i % 3}),
        "list-search": lambda i: ("/api/public/events", {"q": queries[i % len(queries)]}),
        "list-category": lambda i: ("/api/public/events", {"category": categories[i % 4]}),
        "list-range": lambda i: (
            "/api/public/events",
            {"from": f"2026-{1 + i % 12:02d}-01", "to": f"2026-{1 + i % 12:02d}-28"},
        ),
        "detail": lambda i: (f"/api/public/events/{slugs[i % len(slugs)]}", {}),
        "today": lambda i: ("/api/public/today", {}),
        "calendar": lambda i: (
            "/api/public/calendar",
            {"month": f"{month.year}-{1 + i % 12:02d}"},
        ),
    }


def explain_statement(query: str) -> TextClause:
    """Return `EXPLAIN` of the single scan of a text search, as the app builds it."""
    from app.modules.publicapi.query.filters import SiteFilters
    from app.modules.publicapi.query.memory import hits_sql
    from app.modules.search.words import parse

    filters = SiteFilters(now=datetime.now(UTC), words=tuple(parse(query)))
    sql, params = hits_sql(filters)
    return params.statement(f"EXPLAIN (FORMAT JSON) {sql}")


def plan_nodes(plan: Any) -> list[tuple[str, str]]:
    """List `(node type, relation or index)` of a JSON plan, outermost first."""
    found: list[tuple[str, str]] = []
    if isinstance(plan, dict):
        if "Node Type" in plan:
            found.append(
                (plan["Node Type"], plan.get("Index Name") or plan.get("Relation Name", ""))
            )
        for value in plan.values():
            found += plan_nodes(value)
    elif isinstance(plan, list):
        for item in plan:
            found += plan_nodes(item)
    return found


def report(stats: Sequence[Stats]) -> str:
    """Render the latency table."""
    lines = [f"{'route':<14}{'n':>5}{'median':>9}{'p95':>9}{'max':>9}"]
    lines += [
        f"{s.name:<14}{s.count:>5}{s.median:>9.1f}{s.p95:>9.1f}{s.worst:>9.1f}" for s in stats
    ]
    return "\n".join(lines)


def main() -> None:  # pragma: no cover - needs Docker
    """Run the whole check on a throwaway Postgres container and print the table."""
    from scripts.b1_scratch import scratch_app

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=5000)
    parser.add_argument("--requests", type=int, default=MIN_REQUESTS)
    args = parser.parse_args()

    async def run() -> int:
        async with scratch_app(args.events) as (client, slugs, explain):
            stats = [await measure(client, n, r, args.requests) for n, r in routes(slugs).items()]
            print(report(stats))
            print("search plan:", plan_nodes(await explain("Movienight")))
            print(json.dumps({s.name: round(s.p95, 1) for s in stats}))
            return int(any(s.p95 >= LIMIT_MS for s in stats if s.name.startswith("list")))

    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":  # pragma: no cover
    main()
