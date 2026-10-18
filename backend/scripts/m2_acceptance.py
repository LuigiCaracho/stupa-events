"""M2 acceptance run against a host-run API and the dev stack (`python -m scripts.m2_acceptance`).

Criterion (PLAN 16.1, row M2, local reading): a partner account gets 404 on foreign
dossiers, and removing a group in the dev IdP withdraws the access after the next
revalidation. The script logs in through the real OIDC flow, removes `organizer-fsi` from
`events-fsi-organizer` through the Keycloak admin API, checks that the access holds before
the revalidation is due, moves `auth_session.revalidated_at` back by 5 hours, and checks
that the next request shows no `fsi` any more and the dossier is a 404. Then the group comes
back and a new login restores the access. It also observes what the refreshed ID token
carries when a person loses every group (D2) and tries both session revokes.

Only for the local stack. It needs the seeded database (`python -m scripts.seed_dev`).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import Engine, create_engine, text

from app.settings import get_settings
from scripts import acceptance_common as common
from scripts.acceptance_common import API, check, expect, login, step
from scripts.keycloak_admin import Keycloak

common.PREFIX[0] = "m2"
ORGANIZER = "organizer-fsi"
GROUP = "events-fsi-organizer"


def fsi_roles(client: httpx.Client) -> list[tuple[str, str, bool]]:
    """Return the `(slug, role, trusted)` triples `/auth/me` shows for `fsi`."""
    me = expect(client.get("/api/auth/me"), 200, "GET /api/auth/me")
    return [(o["slug"], o["role"], o["trusted"]) for o in me["organizations"] if o["slug"] == "fsi"]


def listed_ids(client: httpx.Client, label: str) -> set[str]:
    """Return the ids of every dossier the person may list, page by page."""
    ids: set[str] = set()
    offset = 0
    while True:
        params = {"limit": 200, "offset": offset}
        page = expect(client.get("/api/events", params=params), 200, f"{label}: GET /api/events")
        ids |= {e["id"] for e in page["items"]}
        offset += len(page["items"])
        if not page["items"] or offset >= page["total"]:
            return ids


def create_fsi_dossier(client: httpx.Client, title: str) -> str:
    """Create an `idea` dossier in `fsi`; return its id."""
    orgs = expect(client.get("/api/organizations", params={"creatable": "true"}), 200, "orgs")
    start = (datetime.now(UTC) + timedelta(days=20)).replace(microsecond=0)
    body = {
        "title": title,
        "startsAt": start.isoformat(),
        "endsAt": (start + timedelta(hours=2)).isoformat(),
        "organizationId": next(o["id"] for o in orgs if o["slug"] == "fsi"),
    }
    return expect(client.post("/api/events", json=body), 201, f"create '{title}'")["id"]


def engine() -> Engine:
    """Return a sync engine on the dev database (`DATABASE_URL` of the environment)."""
    return create_engine(get_settings().database_url.replace("+asyncpg", "+psycopg"))


def age_sessions(sub: str, hours: int = 5) -> int:
    """Set `revalidated_at` of every session of `sub` back by `hours`; return the count."""
    with engine().begin() as conn:
        result = conn.execute(
            text(
                "UPDATE auth_session SET revalidated_at = now() - make_interval(hours => :h) "
                "WHERE principal_id IN (SELECT id FROM principal WHERE email LIKE :e)"
            ),
            {"h": hours, "e": f"{sub}@%"},
        )
        return result.rowcount


def cached_groups(sub: str) -> list[str]:
    """Read the group cache of the person from the database."""
    with engine().connect() as conn:
        row = conn.execute(
            text("SELECT oidc_groups FROM principal WHERE email LIKE :e"), {"e": f"{sub}@%"}
        )
        return list(row.scalar_one())


def withdrawal(keycloak: Keycloak) -> str:
    """Remove the group, age the session, observe the denial; return the dossier id."""
    organizer = login(ORGANIZER)
    check(fsi_roles(organizer) == [("fsi", "organizer", False)], "a: /auth/me names fsi/organizer")
    eid = create_fsi_dossier(organizer, f"M2 Entzug {int(time.time())}")
    check(eid in listed_ids(organizer, "a"), "a: the dossier of fsi is listed")
    keycloak.set_membership(ORGANIZER, GROUP, member=False)
    step("b: removed organizer-fsi from events-fsi-organizer in Keycloak")
    expect(
        organizer.get(f"/api/events/{eid}"), 200, "c: access holds before the revalidation is due"
    )
    check(fsi_roles(organizer) == [("fsi", "organizer", False)], "c: roles unchanged")
    step(f"d: aged {age_sessions(ORGANIZER)} session(s) by 5 hours")
    check(fsi_roles(organizer) == [], "e: /auth/me shows no fsi after the revalidation")
    expect(organizer.get(f"/api/events/{eid}"), 404, "e: the dossier is a 404")
    return eid


def restore(keycloak: Keycloak, eid: str) -> None:
    """Put the group back, log in again, and see the access return."""
    keycloak.set_membership(ORGANIZER, GROUP, member=True)
    again = login(ORGANIZER)
    check(fsi_roles(again) == [("fsi", "organizer", False)], "f: new login, fsi/organizer is back")
    expect(again.get(f"/api/events/{eid}"), 200, "f: the dossier is readable again")


def partner(eid: str) -> None:
    """The partner test account gets 404 on a dossier of another organization."""
    ekhg = login("submitter-ekhg")
    expect(
        ekhg.get(f"/api/events/{eid}"), 404, "partner: submitter-ekhg gets 404 on an fsi dossier"
    )
    for transition in ("T01", "T02"):
        expect(
            ekhg.post(f"/api/events/{eid}/transitions/{transition}", json={}),
            404,
            f"partner: {transition} on the fsi dossier",
        )
    check(eid not in listed_ids(ekhg, "partner"), "partner: the fsi dossier is not in the list")


def observe_empty_claim(keycloak: Keycloak) -> None:
    """Take every group from `submitter-ekhg` and record what the refresh token carries (D2)."""
    groups = ("events-ekhg-submitter", "events-users")
    ekhg = login("submitter-ekhg")
    before = cached_groups("submitter-ekhg")
    for group in groups:
        keycloak.set_membership("submitter-ekhg", group, member=False)
    age_sessions("submitter-ekhg")
    me = expect(ekhg.get("/api/auth/me"), 200, "claim: /auth/me after the revalidation")
    after = cached_groups("submitter-ekhg")
    verdict = "EMPTY claim withdrew the groups" if after == [] else "claim OMITTED, cache kept"
    step(f"claim: cached groups before {before}, after {after} -> {verdict}")
    step(f"claim: organizations after: {[o['slug'] for o in me['organizations']]}")
    for group in groups:
        keycloak.set_membership("submitter-ekhg", group, member=True)


def revokes(keycloak: Keycloak) -> None:
    """Own revoke keeps the running session; the admin revoke ends all sessions of a person."""
    first, second = login("viewer-fsi"), login("viewer-fsi")
    done = expect(first.post("/api/auth/sessions/revoke", json={}), 200, "revoke: own")
    check(done["revoked"] >= 1, f"revoke: {done['revoked']} other session(s) ended")
    expect(first.get("/api/auth/me"), 200, "revoke: the running session stays")
    expect(second.get("/api/auth/me"), 401, "revoke: the other session is anonymous")
    admin = login("admin")
    people = expect(
        admin.get("/api/admin/principals", params={"q": "viewer-fsi"}), 200, "principals"
    )
    pid = people["items"][0]["id"]
    ended = expect(
        admin.post(f"/api/admin/principals/{pid}/sessions/revoke", json={}), 200, "admin revoke"
    )
    check(ended["revoked"] >= 1, f"revoke: admin ended {ended['revoked']} session(s)")
    expect(first.get("/api/auth/me"), 401, "revoke: the next request of the person is 401")


def main() -> None:
    """Run the whole acceptance walk."""
    check(API.startswith(("http://localhost", "http://127.0.0.1")), f"API {API} is local")
    keycloak = Keycloak()
    step(f"realm sync created {keycloak.sync_realm_users()} missing group(s) or user(s)")
    admin = login("admin")
    mappings = expect(admin.get("/api/admin/group-mappings"), 200, "admin reads the mappings")
    check(
        any(m["oidcGroup"] == "events-admin" for m in mappings),
        "events-admin is mapped (admin by group)",
    )
    me = expect(admin.get("/api/auth/me"), 200, "admin /auth/me")
    check("admin" in me["roles"], f"admin role comes from the group: {me['roles']}")
    eid = withdrawal(keycloak)
    restore(keycloak, eid)
    partner(eid)
    observe_empty_claim(keycloak)
    revokes(keycloak)
    step("M2 acceptance: all checks passed")


if __name__ == "__main__":
    main()
