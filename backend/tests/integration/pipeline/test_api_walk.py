"""Random walks over the real API: the invariants of PLAN 4.5 hold after every step.

A seeded walk fires PATCH, revert, poster upload and scan, image exception, the transitions,
the public-status actions and the worker against one dossier, each step as a random person.
After every step: no answer is a 5xx, `approved` and `live` have a clean poster or an
exception, `live` keeps its required fields, and the content of an `approved` dossier only
changes by leaving `approved` (T06 or the next state), never by a field write or a revert.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

import pytest

from tests._support.factories import png_bytes
from tests.integration.events.harness import Api
from worker.advance import advance_states

pytestmark = pytest.mark.integration

USERS = ("organizer-fsi", "submitter-fsi", "editor", "approver-stupa", "approver-fsi", "admin")
CONTENT = (
    "title",
    "summary",
    "descriptionMd",
    "venueText",
    "startsAt",
    "endsAt",
    "ticketUrl",
    "websiteUrl",
    "costText",
)
TRANSITIONS = ("T01", "T02", "T03", "T04", "T05", "T06", "T07")
PATCHES = (
    {"title": "Anderer Titel"},
    {"summary": "Anderer Kurztext"},
    {"summary": None},
    {"descriptionMd": "Mehr [Info](//evil.example/x)"},
    {"venueText": "Aula"},
    {"ticketUrl": "https://tickets.example/x"},
    {"costText": "5 Euro"},
)
REACHED: set[str] = set()
PUBLIC = {"reason": "Grund", "publicReasonCode": "other"}


def digest(event: dict[str, Any]) -> dict[str, Any]:
    return {name: event.get(name) for name in (*CONTENT, "posterId")} | {
        "posterId": (event.get("poster") or {}).get("id")
    }


async def step(api: Api, rng: random.Random, eid: str, posters: list[str]) -> list[int]:
    user = rng.choice(USERS)
    current = await api.get("editor", eid)
    pressing = current["state"] in {"in_review", "approved"} and rng.random() < 0.5
    kind = (
        rng.choice(("patch", "revert"))
        if pressing
        else rng.choice(
            ("patch", "patch", "revert", "poster", "exception", "fire", "fire", "act", "worker")
        )
    )
    if pressing:
        user = rng.choice(("editor", "admin", "approver-stupa"))
    if kind == "patch":
        return [(await api.patch(user, eid, **rng.choice(PATCHES))).status_code]
    if kind == "revert":
        rev = rng.randint(1, current["rev"])
        return [(await api.action(user, eid, "revert-revision", rev=rev)).status_code]
    if kind == "poster":
        colour = f"#{rng.randrange(0x1000000):06x}"
        up = await api.upload_poster(user, eid, data=png_bytes(color=colour))
        if up.status_code == 201:
            posters.append(up.json()["id"])
            if rng.random() < 0.8:
                await api.process_poster(up.json()["id"])
        return [up.status_code]
    if kind == "exception":
        return [
            (
                await api.action(user, eid, "image-exception", reason="Hochschulveranstaltung")
            ).status_code
        ]
    if kind == "fire":
        body: dict[str, Any] = {"note": "Notiz"} if rng.random() < 0.7 else {}
        if rng.random() < 0.3:
            body["publishAt"] = (
                datetime.fromisoformat(current["startsAt"]) - timedelta(days=1)
            ).isoformat()
        offered = [t for t in current["allowedTransitions"] if t != "T11"]
        if offered and rng.random() < 0.7:
            user, name = "editor", rng.choice(offered)
        else:
            name = "T11" if rng.random() < 0.03 else rng.choice(TRANSITIONS)
        return [(await api.fire(user, eid, name, **body)).status_code]
    if kind == "act":
        name = rng.choice(
            ("cancel", "postpone", "reinstate", "acknowledge-changes", "confirm-flyer")
        )
        return [(await api.action(user, eid, name, **PUBLIC)).status_code]
    when = datetime.fromisoformat(current["startsAt"]) + timedelta(days=rng.choice((-2, 0, 1, 60)))
    await advance_states({"advance_sessionmaker": api.maker, "redis": api.pool}, now=when)
    return []


def check(before: dict[str, Any], after: dict[str, Any]) -> None:
    state = after["state"]
    if state in {"approved", "live"}:
        poster = after.get("poster")
        assert after.get("imageException") or (poster and poster["scanStatus"] == "clean"), after
    if state == "live":
        assert after["summary"] and after["title"], after
    if before["state"] == "approved" and state == "approved":
        assert digest(before) == digest(after)


@pytest.mark.parametrize("seed", range(16))
async def test_no_walk_breaks_the_invariants(api: Api, seed: int) -> None:
    rng = random.Random(seed)
    event = await api.create_event()
    eid = event["id"]
    posters: list[str] = []
    before = await api.get("editor", eid)
    trace: list[str] = []
    for index in range(40):
        codes = await step(api, rng, eid, posters)
        trace.append(f"{index}:{codes}")
        assert all(code < 500 for code in codes), trace
        after = await api.get("editor", eid)
        try:
            check(before, after)
        except AssertionError:
            pytest.fail(f"seed {seed} step {index}: {trace}\n{before}\n{after}")
        REACHED.add(after["state"])
        before = after


def test_the_walks_reach_the_states_that_matter() -> None:
    assert {"approved", "live"} <= REACHED
