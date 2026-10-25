"""C acceptance data against the host API: `python -m scripts.c_acceptance setup|check|teardown`.

Criteria (PLAN 16.3 C2 to C4) on real data instead of route mocks: `setup` pins Davos, Ischgl,
Europapark and Straßburg by hand (I23, source `pin`, precision `building`), because their
Nominatim lookup is Luis' `pin_venues --live` run (W-C6), and publishes events there and in
building 9 (Kinosaal 9-133, Maker Space 9-229, FSI 9-U09) today, plus a cancelled event in
building 9 and one at a private venue with a coordinate in building 9. `check` reads the public
map and campus routes without a cookie. `teardown` clears the hand pins and deactivates the
private venue, so the dev data matches `docs/VENUES-PINNED.md` again. Only for the local stack;
the state of a run lives in `--state`.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from scripts import dossier_api as dossier
from scripts.acceptance_common import PREFIX, check, expect, login, step
from scripts.m5_live import anonymous

PREFIX[0] = "c"
DESTINATIONS = {
    "davos": (46.8027, 9.836),
    "ischgl": (47.0012, 10.2919),
    "europapark": (48.266, 7.7221),
    "strassburg": (48.5734, 7.7521),
}
BUILDING_9 = ("kinosaal-9-133", "maker-space-9-229", "fsi-9-u09")
PRIVATE_SLUG = "c-abnahme-privat-9"
PRIVATE_POINT = (48.48291, 9.18731)


def venues(admin: httpx.Client) -> dict[str, dict[str, Any]]:
    """Return the venues of the admin API by slug."""
    return {row["slug"]: row for row in expect(admin.get("/api/admin/venues"), 200, "venues")}


def publish_at(
    organizer: httpx.Client, title: str, venue_id: str, start: datetime, *, cancel: bool = False
) -> str:
    """Create, place, publish (and optionally cancel) an FSI event; return its id."""
    eid = dossier.create(organizer, title)
    dossier.patch(
        organizer,
        eid,
        venueId=venue_id,
        startsAt=start.isoformat(),
        endsAt=(start + timedelta(hours=2)).isoformat(),
    )
    dossier.act(organizer, eid, "publish")
    if cancel:
        dossier.act(organizer, eid, "cancel", reason="Saal belegt", publicReasonCode="room")
    return eid


def private_venue(admin: httpx.Client, known: dict[str, dict[str, Any]]) -> str:
    """Return the id of the private test venue in building 9, active and with a coordinate."""
    body = {
        "lat": PRIVATE_POINT[0],
        "lon": PRIVATE_POINT[1],
        "buildingNo": "9",
        "publicPrecision": "building",
        "isPrivate": True,
        "active": True,
    }
    if PRIVATE_SLUG in known:
        row = known[PRIVATE_SLUG]
        expect(admin.patch(f"/api/admin/venues/{row['id']}", json=body), 200, "private venue")
        return row["id"]
    created = admin.post(
        "/api/admin/venues", json={"slug": PRIVATE_SLUG, "name": "C-Abnahme privat", **body}
    )
    return expect(created, 201, "private venue")["id"]


def setup(state: Path) -> None:
    """Pin the destinations and publish the events of the run."""
    admin, organizer = login("admin"), login("organizer-fsi")
    known = venues(admin)
    saved = {
        slug: {k: known[slug][k] for k in ("lat", "lon", "publicPrecision")}
        for slug in DESTINATIONS
    }
    for slug, (lat, lon) in DESTINATIONS.items():
        body = {"lat": lat, "lon": lon, "publicPrecision": "building", "geocodeSource": "pin"}
        expect(admin.patch(f"/api/admin/venues/{known[slug]['id']}", json=body), 200, f"pin {slug}")
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    soon = now + timedelta(hours=1)
    titles = {"building9": [], "destinations": [], "excluded": []}
    for slug in BUILDING_9:
        eid = publish_at(organizer, f"C Campus {slug}", known[slug]["id"], soon)
        titles["building9"].append(
            expect(organizer.get(f"/api/events/{eid}"), 200, "read")["title"]
        )
    for days, slug in enumerate(DESTINATIONS, start=5):
        eid = publish_at(
            organizer, f"C Reise {slug}", known[slug]["id"], now + timedelta(days=days)
        )
        titles["destinations"].append(
            expect(organizer.get(f"/api/events/{eid}"), 200, "read")["title"]
        )
    for title, venue_id, cancel in (
        ("C abgesagt 9-133", known["kinosaal-9-133"]["id"], True),
        ("C privat 9", private_venue(admin, known), False),
    ):
        eid = publish_at(organizer, title, venue_id, soon, cancel=cancel)
        titles["excluded"].append(expect(organizer.get(f"/api/events/{eid}"), 200, "read")["title"])
    state.write_text(json.dumps({"saved": saved, "titles": titles}, indent=2), encoding="utf-8")
    step(f"setup done, state in {state}")


def check_public(state: Path) -> None:
    """Read the map and campus routes anonymously and check them against the run."""
    titles = json.loads(state.read_text(encoding="utf-8"))["titles"]
    client = anonymous()
    world = client.get("/api/public/map/events")
    check("set-cookie" not in world.headers, "map/events sets no cookie")
    features = expect(world, 200, "map/events")["features"]
    names = {f["properties"]["venueName"] for f in features}
    for name in ("Davos", "Ischgl", "Europapark", "Straßburg"):
        check(name in names, f"world map has {name}")
    by_title = {f["properties"]["title"]: f for f in features}
    for title in titles["destinations"]:
        check(title in by_title, f"world map has '{title}'")
    check(
        not any(t in by_title for t in titles["excluded"][1:]),
        "the private venue is not on the map",
    )
    campus_list = client.get("/api/public/campus/events", params={"building": "9"}).text
    body = world.text + client.get("/api/public/campus/buildings").text + campus_list
    check("C-Abnahme privat" not in body and titles["excluded"][1] not in body, "no private trace")
    buildings = expect(client.get("/api/public/campus/buildings"), 200, "campus/buildings")
    nine = next(f for f in buildings["features"] if f["properties"]["buildingNo"] == "9")
    check(
        nine["properties"]["count"] == 3, f"building 9 counts 3 (got {nine['properties']['count']})"
    )
    listed = expect(client.get("/api/public/campus/events", params={"building": "9"}), 200, "list")
    got = sorted(item["title"] for item in listed["items"] if item["status"] != "cancelled")
    check(got == sorted(titles["building9"]), f"building 9 lists the three events ({got})")
    cancelled = [
        item["status"] for item in listed["items"] if item["title"] == titles["excluded"][0]
    ]
    check(cancelled in ([], ["cancelled"]), "the cancelled event is marked cancelled, not counted")
    step("check done")


def teardown(state: Path) -> None:
    """Clear the hand pins and deactivate the private venue."""
    admin = login("admin")
    known = venues(admin)
    saved = json.loads(state.read_text(encoding="utf-8"))["saved"]
    for slug, before in saved.items():
        body = {
            "lat": before["lat"],
            "lon": before["lon"],
            "publicPrecision": before["publicPrecision"],
        }
        expect(
            admin.patch(f"/api/admin/venues/{known[slug]['id']}", json=body), 200, f"unpin {slug}"
        )
    if PRIVATE_SLUG in known:
        row = known[PRIVATE_SLUG]
        expect(
            admin.patch(f"/api/admin/venues/{row['id']}", json={"active": False}), 200, "deactivate"
        )
    step("teardown done")


def main() -> None:
    """Run one step of the C acceptance data."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("setup", "check", "teardown"))
    parser.add_argument("--state", type=Path, default=Path("/tmp/c-acceptance.json"))
    args = parser.parse_args()
    {"setup": setup, "check": check_public, "teardown": teardown}[args.step](args.state)


if __name__ == "__main__":
    main()
