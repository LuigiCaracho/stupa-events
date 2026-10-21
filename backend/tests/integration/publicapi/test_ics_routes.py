"""The calendar routes over HTTP: headers, ETag, categories, cancellations and the live path."""

from __future__ import annotations

import pytest
from icalendar import Calendar

from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def ics(api: Api, path: str, **kw: object):  # noqa: ANN201
    return await api.request(None, "GET", path, **kw)


def uids(body: bytes) -> list[str]:
    return [str(e["UID"]).split("@")[0] for e in Calendar.from_ical(body).walk("VEVENT")]


async def test_all_ics_has_the_headers_and_one_event_per_public_dossier(api: Api) -> None:
    one = await api.to_state("live")
    response = await ics(api, "/ics/all.ics")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/calendar; charset=utf-8"
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.headers["content-disposition"] == 'inline; filename="stupa-events.ics"'
    assert response.headers["x-robots-tag"] == "noindex" and "set-cookie" not in response.headers
    assert "access-control-allow-origin" not in response.headers
    assert uids(response.content) == [one["id"]]
    body = response.content.decode()
    assert "STATUS:CONFIRMED" in body and "LOCATION:Kinosaal 9-133" in body
    assert "CATEGORIES:Kino" in body and f"URL:http://localhost:8081/e/{one['slug']}" in body
    again = await ics(api, "/ics/all.ics", headers={"If-None-Match": response.headers["etag"]})
    assert again.status_code == 304 and again.content == b""
    assert (await ics(api, "/ics/all.ics?x=1&token=abc")).content == response.content


async def test_category_calendars_include_children_and_ignore_inactive_flags(api: Api) -> None:
    fsi = await api.to_state(
        "live", primaryCategoryId=api.category_ids["fachschaft-informatik-fsi"]
    )
    kino = await api.to_state("live", title="Kino")
    parent = await ics(api, "/ics/k/fachschaft.ics")
    assert uids(parent.content) == [fsi["id"]]
    child = await ics(api, "/ics/k/fachschaft-informatik-fsi.ics")
    assert uids(child.content) == [fsi["id"]]
    assert "X-WR-CALNAME:STUPA Events: Fachschaft Informatik" in child.content.decode()
    only_kino = await ics(api, "/ics/k/kino.ics")
    assert uids(only_kino.content) == [kino["id"]]
    await api.sql("UPDATE category SET active = false WHERE slug = 'kino'")
    try:
        assert (await ics(api, "/ics/k/kino.ics")).status_code == 200
    finally:
        await api.sql("UPDATE category SET active = true WHERE slug = 'kino'")
    empty = await ics(api, "/ics/k/konzert.ics")
    assert empty.status_code == 200 and uids(empty.content) == []


@pytest.mark.parametrize("slug", ["gibt-es-nicht", "Gross", "-x", "a" * 61, "a_b"])
async def test_unknown_or_malformed_slugs_are_404_problem_json(api: Api, slug: str) -> None:
    response = await ics(api, f"/ics/k/{slug}.ics")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "set-cookie" not in response.headers and response.headers["x-robots-tag"] == "noindex"


async def test_cancellations_and_postponements_stay_in_the_calendar(api: Api) -> None:
    event = await api.to_state("live")
    cancelled = await api.action(
        "editor",
        event["id"],
        "cancel",
        reason="Saal weg",
        publicReasonCode="room",
        publicReasonText="Saal weg",
    )
    assert cancelled.status_code == 200
    body = (await ics(api, "/ics/all.ics")).content.decode()
    assert "STATUS:CANCELLED" in body and "Abgesagt: Saal weg" in body and "SEQUENCE:2" in body
    assert "Saal weg" in body and "Hausmeister" not in body


async def test_withdrawn_and_draft_dossiers_are_not_in_the_calendar(api: Api) -> None:
    await api.to_state("approved")
    await api.create_event(title="Entwurf")
    assert uids((await ics(api, "/ics/all.ics")).content) == []


async def test_postpone_with_a_new_date_keeps_the_uid_and_raises_the_sequence(api: Api) -> None:
    event = await api.to_state("live")
    first = (await ics(api, "/ics/all.ics")).content
    moved = await api.action(
        "editor",
        event["id"],
        "postpone",
        reason="Verschoben",
        newStartsAt="2027-03-02T19:00:00Z",
        newEndsAt="2027-03-02T21:00:00Z",
        publicReasonCode="other",
    )
    assert moved.status_code == 200, moved.text
    second = (await ics(api, "/ics/all.ics")).content
    assert uids(first) == uids(second) and first != second
    text = second.decode()
    assert "DTSTART;TZID=Europe/Berlin:20270302T200000" in text and "STATUS:TENTATIVE" in text
    assert "SEQUENCE:" in text and "SEQUENCE:1" not in text


async def test_the_window_keeps_three_months_back_and_twelve_ahead(api: Api) -> None:
    old = await api.to_state("live", title="Lange her")
    far = await api.to_state("live", title="Sehr weit")
    near = await api.to_state("live", title="Gerade vorbei")
    await api.sql(
        "UPDATE event SET starts_at = now() - interval '200 days', ends_at = now() - interval '199 days' WHERE id = :e",
        e=old["id"],
    )
    await api.sql(
        "UPDATE event SET starts_at = now() + interval '400 days', ends_at = now() + interval '401 days' WHERE id = :e",
        e=far["id"],
    )
    await api.sql(
        "UPDATE event SET starts_at = now() - interval '40 days', ends_at = now() - interval '39 days' WHERE id = :e",
        e=near["id"],
    )
    assert uids((await ics(api, "/ics/all.ics")).content) == [near["id"]]


async def test_if_none_match_with_another_validator_gets_the_calendar(api: Api) -> None:
    await api.to_state("live")
    other = await ics(api, "/ics/all.ics", headers={"If-None-Match": '"nope"'})
    assert other.status_code == 200 and other.content
    wildcard = await ics(api, "/ics/all.ics", headers={"If-None-Match": "*"})
    assert wildcard.status_code == 304


@pytest.mark.parametrize("path", ["/ics/all.ics", "/ics/k/kino.ics", "/api/public/feed/events"])
async def test_head_answers_like_get_without_a_body(api: Api, path: str) -> None:
    await api.to_state("live")
    got = await api.request(None, "GET", path)
    head = await api.request(None, "HEAD", path)
    assert head.status_code == 200 and head.content == b""
    assert head.headers["etag"] == got.headers["etag"]
