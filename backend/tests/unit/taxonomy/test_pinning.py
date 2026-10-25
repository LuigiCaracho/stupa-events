"""The pinning plan: who gets a coordinate from where, and who stays hidden."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

from app.modules.taxonomy.campus import campus_rows
from app.modules.taxonomy.models import Venue
from app.modules.taxonomy.pinning import PLACE_QUERIES, plan, report
from app.modules.taxonomy.venue_reference import VENUES

POLYGONS = {r["number"]: json.loads(r["geometry"]) for r in campus_rows()}


def venue(slug: str, **over: Any) -> Venue:
    return Venue(slug=slug, name=slug, active=True, is_private=False, lat=None, **over)


def decisions(*venues: Venue) -> dict[str, Any]:
    return {d.slug: d for d in plan(venues, POLYGONS)}


def test_a_campus_venue_gets_the_centroid_of_its_building() -> None:
    d = decisions(venue("kino", building_no="9"))["kino"]
    assert d.action == "campus" and d.building == "9" and d.query is None
    assert Decimal("9.17") < d.lon < Decimal("9.20") and Decimal("48.47") < d.lat < Decimal("48.49")


def test_a_venue_with_street_and_town_is_geocoded_by_its_address() -> None:
    d = decisions(venue("a", address="Alteburgstraße 150", city="Reutlingen", postcode="72762"))[
        "a"
    ]
    assert (d.action, d.query) == ("geocode", "Alteburgstraße 150, 72762 Reutlingen")


def test_a_curated_destination_is_geocoded_by_name() -> None:
    d = decisions(venue("davos"), venue("europapark", city="Rust"))
    assert (d["davos"].action, d["davos"].query) == ("place", "Davos")
    assert d["europapark"].action == "place" and d["europapark"].query == "Europa-Park, Rust"


def test_the_rest_stays_hidden() -> None:
    d = decisions(
        venue("rappen", address="Ob. Gerberstraße 6"),
        venue("building-17", building_no="17"),
        venue("schwarzwald"),
    )
    assert {x.action for x in d.values()} == {"hidden"}


def test_private_inactive_and_pinned_venues_are_left_alone() -> None:
    private = venue("p", address="Weg 1", city="Ort")
    private.is_private = True
    inactive = venue("i", building_no="9")
    inactive.active = False
    pinned = venue("x", building_no="9")
    pinned.lat = Decimal("48.4")
    d = decisions(private, inactive, pinned)
    assert (d["p"].action, d["i"].action, d["x"].action) == ("private", "inactive", "pinned")


def test_a_venue_hidden_by_hand_after_a_lookup_is_not_geocoded_again() -> None:
    manual = venue(
        "m", address="Weg 1", city="Ort", geocode_source="manual", public_precision="hidden"
    )
    fresh = venue("f", address="Weg 1", city="Ort", public_precision="hidden")
    d = decisions(manual, fresh)
    assert (d["m"].action, d["f"].action) == ("kept_hidden", "geocode")


def test_the_reference_venues_split_as_planned() -> None:
    rows = [Venue(**{**v, "active": True, "is_private": False, "lat": None}) for v in VENUES]
    by_action: dict[str, list[str]] = {}
    for d in plan(rows, POLYGONS):
        by_action.setdefault(d.action, []).append(d.slug)
    assert {"kinosaal-9-133", "maker-space-9-229", "fsi-9-u09", "texoversum"} <= set(
        by_action["campus"]
    )
    assert "hochschule-reutlingen" in by_action["geocode"]
    assert {"davos", "ischgl", "europapark", "strassburg"} <= set(by_action["place"])
    assert "raum-17-u14" in by_action["hidden"] and "zum-alten-rappen" in by_action["hidden"]
    assert set(PLACE_QUERIES) - {"serfaus-fiss-ladis"} <= set(by_action["place"])


def test_place_queries_hold_no_region_and_no_private_venue() -> None:
    forbidden = {"schwarzwald", "arosa-lenzerheide", "hades", "arcadia", "franz-k"}
    assert not forbidden & set(PLACE_QUERIES)
    known = {v["slug"]: v for v in VENUES}
    assert set(PLACE_QUERIES) <= set(known)
    assert not any(known[s].get("is_private") for s in PLACE_QUERIES)


def test_the_report_is_a_markdown_table_with_rounded_coordinates() -> None:
    d = decisions(venue("kino", building_no="9"))["kino"]
    table = report([(d, "gepinnt", d.lat, d.lon)])
    lines = table.splitlines()
    assert lines[0].startswith("| Slug") and lines[1].startswith("|---")
    assert "| `kino` |" in lines[2] and "48.483" in lines[2] and "9.187" in lines[2]


@pytest.mark.parametrize("slug", sorted(PLACE_QUERIES))
def test_every_place_query_is_a_plain_name(slug: str) -> None:
    assert PLACE_QUERIES[slug].strip() and "\n" not in PLACE_QUERIES[slug]
