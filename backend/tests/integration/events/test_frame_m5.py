"""The frame of a dossier in M5: venue confirmation, facts, all-day events and the calendar."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


async def test_an_unconfirmed_free_venue_text_publishes_but_stays_out_of_the_feed(
    api: Api,
) -> None:
    event = await api.create_event()
    eid = event["id"]
    published = await api.act("organizer-fsi", eid, "publish")
    assert published.status_code == 200
    hints = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/hints")).json()
    assert {"code": "location_unconfirmed", "severity": "warn", "field": "venueText"} in hints[
        "items"
    ]
    item = (await api.request(None, "GET", "/api/public/feed/events")).json()["items"][0]
    assert item["venueText"] is None and item["venue"] is None
    assert (await api.get("editor", eid))["locationPrecision"] == "hidden"
    confirmed = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/actions/confirm-location",
        json={"precision": "exact"},
    )
    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["locationPrecision"] == "exact" and body["locationConfirmedAt"]
    shown = (await api.request(None, "GET", "/api/public/feed/events")).json()["items"][0]
    assert shown["venueText"] == "Kinosaal 9-133"


async def test_confirm_location_rules(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    url = f"/api/events/{eid}/actions/confirm-location"
    hidden = await api.request("editor", "POST", url, json={"precision": "hidden"})
    assert hidden.status_code == 422
    forbidden = await api.request("viewer-fsi", "POST", url, json={"precision": "exact"})
    assert forbidden.status_code == 403
    stranger = await api.request("organizer-makers", "POST", url, json={"precision": "exact"})
    assert stranger.status_code == 404
    venue = await api.sql("SELECT id FROM venue WHERE NOT is_private LIMIT 1")
    await api.sql("UPDATE event SET venue_id = :v WHERE id = :e", v=venue[0][0], e=eid)
    no_text = await api.request("editor", "POST", url, json={"precision": "exact"})
    assert no_text.status_code == 409 and no_text.json()["code"] == "invalid_state"
    audit = await api.sql("SELECT data FROM audit_entry WHERE action = 'event_location_confirm'")
    assert audit == []


async def test_changing_the_venue_text_resets_the_confirmation(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    await api.request(
        "editor",
        "POST",
        f"/api/events/{eid}/actions/confirm-location",
        json={"precision": "building"},
    )
    patched = await api.patch("organizer-fsi", eid, venueText="Anderer Saal")
    assert patched.status_code == 200
    assert patched.json()["locationPrecision"] == "hidden"
    assert patched.json()["locationConfirmedAt"] is None


async def test_when_published_the_confirmation_raises_public_seq_and_the_view_follows(
    api: Api,
) -> None:
    live = await api.to_state("published")
    eid = live["id"]
    seq = (await api.sql("SELECT public_seq FROM event WHERE id = :e", e=eid))[0][0]
    shown = await api.request("editor", "GET", f"/api/events/{eid}")
    assert shown.json()["locationPrecision"] == "building"
    await api.sql("UPDATE event SET location_precision = 'hidden' WHERE id = :e", e=eid)
    feed = (await api.request(None, "GET", "/api/public/feed/events")).json()["items"][0]
    assert feed["venueText"] is None and feed["venue"] is None
    again = await api.request(
        "editor", "POST", f"/api/events/{eid}/actions/confirm-location", json={"precision": "exact"}
    )
    assert again.status_code == 200
    assert (await api.sql("SELECT public_seq FROM event WHERE id = :e", e=eid))[0][0] == seq + 1
    feed = (await api.request(None, "GET", "/api/public/feed/events")).json()["items"][0]
    assert feed["venueText"] == "Kinosaal 9-133" and feed["venue"]["name"] == "Kinosaal 9-133"
    assert feed["venue"]["address"] is None


async def test_facts_api(api: Api) -> None:
    event = await api.create_event(primaryCategoryId=api.category_ids["party"])
    eid = event["id"]
    url = f"/api/events/{eid}/facts"
    no_header = await api.request("organizer-fsi", "PUT", url, json={"ageLimit": 18})
    assert no_header.status_code == 428
    headers = {"If-Match": f'"{event["rev"]}"'}
    unknown = await api.request(
        "organizer-fsi", "PUT", url, json={"agendaMd": "x"}, headers=headers
    )
    assert unknown.status_code == 422
    bad_age = await api.request("organizer-fsi", "PUT", url, json={"ageLimit": 17}, headers=headers)
    assert bad_age.status_code == 422
    ok = await api.request(
        "organizer-fsi", "PUT", url, json={"ageLimit": 18, "capacity": 120}, headers=headers
    )
    assert ok.status_code == 200 and ok.json()["facts"] == {"ageLimit": 18, "capacity": 120}
    stale = await api.request("organizer-fsi", "PUT", url, json={"ageLimit": 18}, headers=headers)
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"
    archived = await api.to_state("archived")
    locked = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/events/{archived['id']}/facts",
        json={"capacity": 1},
        headers={"If-Match": f'"{archived["rev"]}"'},
    )
    assert locked.status_code == 409 and locked.json()["code"] == "field_locked"


async def test_a_party_without_an_age_limit_is_a_hint_not_a_lock(api: Api) -> None:
    event = await api.create_event(primaryCategoryId=api.category_ids["party"])
    eid = event["id"]
    codes = lambda hints: [h["code"] for h in hints["items"]]  # noqa: E731
    hints = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/hints")).json()
    assert "facts_incomplete" in codes(hints)
    assert (await api.act("organizer-fsi", eid, "publish")).status_code == 200
    rev = (await api.get("editor", eid))["rev"]
    await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/events/{eid}/facts",
        json={"ageLimit": 16},
        headers={"If-Match": f'"{rev}"'},
    )
    hints = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/hints")).json()
    assert "facts_incomplete" not in codes(hints)


async def test_a_trip_needs_min_not_above_max_and_a_category_change_drops_foreign_keys(
    api: Api,
) -> None:
    event = await api.create_event(primaryCategoryId=api.category_ids["ausfahrt"])
    eid = event["id"]
    url = f"/api/events/{eid}/facts"
    ok = await api.request(
        "organizer-fsi",
        "PUT",
        url,
        json={"minParticipants": 9, "maxParticipants": 4, "meetingPoint": "Bahnhof"},
        headers={"If-Match": f'"{event["rev"]}"'},
    )
    assert ok.status_code == 200
    moved = await api.patch("organizer-fsi", eid, primaryCategoryId=api.category_ids["kino"])
    assert moved.status_code == 200
    assert moved.json()["facts"] == {} and moved.json()["factsDropped"] == [
        "maxParticipants",
        "meetingPoint",
        "minParticipants",
    ]


async def test_all_day_event_api(api: Api) -> None:
    created = await api.request(
        "organizer-fsi",
        "POST",
        "/api/events",
        json={
            "title": "Tag der offenen Tür",
            "allDay": True,
            "startsOn": "2026-10-25",
            "endsOn": "2026-10-26",
            "organizationId": api.org_ids["fsi"],
            "venueText": "Campus",
        },
    )
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["allDay"] and event["startsOn"] == "2026-10-25" and event["endsOn"] == "2026-10-26"
    assert event["startsAt"] == "2026-10-24T22:00:00Z" and event["endsAt"] == "2026-10-26T23:00:00Z"
    assert event["endEstimated"] is False
    one_day = await api.request(
        "organizer-fsi",
        "POST",
        "/api/events",
        json={
            "title": "Ein Tag",
            "allDay": True,
            "startsOn": "2026-03-28",
            "organizationId": api.org_ids["fsi"],
        },
    )
    assert (
        one_day.json()["endsOn"] == "2026-03-28"
        and one_day.json()["endsAt"] == "2026-03-28T23:00:00Z"
    )
    for bad in (
        {"allDay": True},
        {"allDay": True, "startsOn": "2026-10-25", "startsAt": future().isoformat()},
        {"allDay": True, "startsOn": "2026-10-25", "endsOn": "2026-10-24"},
        {"startsAt": future().isoformat(), "startsOn": "2026-10-25"},
        {},
    ):
        response = await api.request(
            "organizer-fsi",
            "POST",
            "/api/events",
            json={"title": "x", "organizationId": api.org_ids["fsi"], **bad},
        )
        assert response.status_code == 422, bad


async def test_all_day_patch_rules(api: Api) -> None:
    timed = await api.create_event()
    eid = timed["id"]
    switched = await api.patch("organizer-fsi", eid, allDay=True, startsOn="2026-11-03")
    assert switched.status_code == 200 and switched.json()["endsOn"] == "2026-11-03"
    moved = await api.patch("organizer-fsi", eid, startsOn="2026-11-05")
    assert moved.json()["startsOn"] == "2026-11-05" and moved.json()["endsOn"] == "2026-11-05"
    longer = await api.patch("organizer-fsi", eid, endsOn="2026-11-07")
    assert longer.json()["endsAt"] == "2026-11-07T23:00:00Z"
    mixed = await api.patch("organizer-fsi", eid, startsAt=future().isoformat())
    assert mixed.status_code == 422
    back_without_times = await api.patch("organizer-fsi", eid, allDay=False)
    assert back_without_times.status_code == 422
    assert back_without_times.json()["code"] == "times_required"
    back = await api.patch(
        "organizer-fsi",
        eid,
        allDay=False,
        startsAt=future().isoformat(),
        endsAt=future(14, 3).isoformat(),
    )
    assert back.status_code == 200 and back.json()["startsOn"] is None
    days_on_timed = await api.patch("organizer-fsi", eid, startsOn="2026-11-05")
    assert days_on_timed.status_code == 422
    nothing = await api.patch("organizer-fsi", eid, allDay=None)
    assert nothing.status_code == 422


async def test_calendar_view(api: Api) -> None:
    mine = await api.create_event(title="Eigener Termin")
    other = await api.create_event(user="organizer-makers", org="makers", title="Fremder Termin")
    assert other["title"] == "Fremder Termin"
    window = {
        "view": "calendar",
        "from": (datetime.now(UTC).date()).isoformat(),
        "to": future(40).date().isoformat(),
    }
    found = await api.request("organizer-fsi", "GET", "/api/events", params=window)
    assert found.status_code == 200, found.text
    body = found.json()
    assert [e["id"] for e in body["entries"]] == [mine["id"]]
    entry = body["entries"][0]
    assert entry["organization"] == {"slug": "fsi", "short": "FSI", "colorToken": "petrol"}
    assert entry["venueName"] == "Kinosaal 9-133" and entry["howtoUnverified"] is False
    assert body["from"] == window["from"] and body["truncated"] is False
    everything = await api.request("editor", "GET", "/api/events", params=window)
    assert len(everything.json()["entries"]) == 2
    archived_only = await api.request(
        "editor", "GET", "/api/events", params={**window, "state": "archived"}
    )
    assert archived_only.json()["entries"] == []


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"view": "calendar"}, "range_required"),
        ({"view": "calendar", "from": "2026-10-01"}, "range_required"),
        ({"view": "calendar", "from": "2026-10-10", "to": "2026-10-01"}, "range_invalid"),
        ({"view": "calendar", "from": "2026-01-01", "to": "2026-04-11"}, "range_too_large"),
    ],
)
async def test_calendar_range_errors(api: Api, params: dict[str, str], code: str) -> None:
    response = await api.request("editor", "GET", "/api/events", params=params)
    assert response.status_code == 422 and response.json()["code"] == code


async def test_calendar_range_of_exactly_one_hundred_days_is_allowed_and_overlap_counts(
    api: Api,
) -> None:
    event = await api.create_event(
        startsAt="2026-12-31T22:00:00Z", endsAt="2027-01-01T01:00:00Z", title="Silvester"
    )
    params = {"view": "calendar", "from": "2027-01-01", "to": "2027-04-10"}
    hit = await api.request("editor", "GET", "/api/events", params=params)
    assert hit.status_code == 200 and [e["id"] for e in hit.json()["entries"]] == [event["id"]]
    miss = await api.request(
        "editor", "GET", "/api/events", params={**params, "from": "2027-01-02", "to": "2027-04-11"}
    )
    assert miss.json()["entries"] == []
