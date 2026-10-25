"""Plan and report of the one-off pinning of the venues (`scripts/pin_venues.py`).

`plan` is a pure function: it reads venue rows and the campus polygons and decides, per venue,
how it gets a coordinate. A private or inactive venue is never touched, nor is one a human hid after a
lookup (`hidden` with a geocode source); a venue with a coordinate keeps it, a venue of a drawn campus building gets the polygon's centroid, a venue
with street and town is geocoded, a curated destination is geocoded by its name, everything
else stays `hidden`. Nothing here talks to the network or the database.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from functools import partial
from typing import Any, Literal

from app.modules.geocode.service import address_query
from app.modules.taxonomy.campus import centroid
from app.modules.taxonomy.models import Venue
from app.shared.errors import ValidationProblem

PLACE_QUERIES: Mapping[str, str] = {
    "davos": "Davos",
    "ischgl": "Ischgl",
    "europapark": "Europa-Park, Rust",
    "strassburg": "Straßburg",
    "montafon": "Montafon",
    "flumserberg": "Flumserberg",
    "serfaus-fiss-ladis": "Serfaus-Fiss-Ladis",
}
Action = Literal[
    "private", "inactive", "kept_hidden", "pinned", "campus", "geocode", "place", "hidden"
]
SOURCES: Mapping[Action, str] = {
    "private": "privat, bleibt verborgen",
    "inactive": "inaktiv, übersprungen",
    "kept_hidden": "von Hand verborgen, bleibt verborgen",
    "pinned": "hat schon eine Koordinate",
    "campus": "Gebäudepolygon",
    "geocode": "Adresse (Nominatim)",
    "place": "Ortsname (Nominatim)",
    "hidden": "keine Adresse, kein Polygon",
}


@dataclass(frozen=True, slots=True)
class Decision:
    """What happens to one venue; `lat` and `lon` are set for the campus case."""

    slug: str
    name: str
    action: Action
    query: str | None = None
    building: str | None = None
    lat: Decimal | None = None
    lon: Decimal | None = None

    @property
    def needs_network(self) -> bool:
        """Tell if the venue is pinned by a Nominatim lookup."""
        return self.action in ("geocode", "place")


def _six(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.000001"))


def _decide(venue: Venue, polygons: Mapping[str, dict[str, Any]]) -> Decision:
    decide = partial(Decision, venue.slug, venue.name)
    if not venue.active:
        return decide(action="inactive")
    if venue.is_private:
        return decide(action="private")
    if venue.lat is not None:
        return decide(action="pinned")
    if venue.public_precision == "hidden" and venue.geocode_source is not None:
        return decide(action="kept_hidden")
    if venue.building_no is not None and venue.building_no in polygons:
        lon, lat = centroid(polygons[venue.building_no])
        return decide(action="campus", building=venue.building_no, lat=_six(lat), lon=_six(lon))
    try:
        return decide(
            action="geocode", query=address_query(venue.address, venue.postcode, venue.city)
        )
    except ValidationProblem:
        pass
    if venue.slug in PLACE_QUERIES:
        return decide(action="place", query=PLACE_QUERIES[venue.slug])
    return decide(action="hidden")


def plan(venues: Iterable[Venue], polygons: Mapping[str, dict[str, Any]]) -> list[Decision]:
    """Decide for every venue, in the order of the input."""
    return [_decide(venue, polygons) for venue in venues]


def _cell(value: Decimal | None) -> str:
    return f"{value:.3f}" if value is not None else ""


def report(rows: Iterable[tuple[Decision, str, Decimal | None, Decimal | None]]) -> str:
    """Render the decisions with their outcome as a Markdown table (coordinates rounded)."""
    lines = [
        "| Slug | Name | Entscheidung | Quelle | Ergebnis | Breite | Länge |",
        "|---|---|---|---|---|---|---|",
    ]
    for decision, outcome, lat, lon in rows:
        lines.append(
            f"| `{decision.slug}` | {decision.name} | {decision.action} "
            f"| {SOURCES[decision.action]} | {outcome} | {_cell(lat)} | {_cell(lon)} |"
        )
    return "\n".join(lines) + "\n"
