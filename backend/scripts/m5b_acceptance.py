"""M5b acceptance run against a host-run API and the dev stack (`python -m scripts.m5b_acceptance`).

Criterion (M5b contract 1 and 2): a dossier has three states; the organization publishes
with title, start and organization alone; a missing poster is a hint and the feed says
`image: null`; the editorial team restores; cancel and reinstate change the public status;
the worker archives twelve hours after the end. Rights per role, the removed pipeline routes,
"Neu aus Vorlage", format and library, and the cache invalidation on a category rename are
checked as well (`m5b_dossier`, `m5b_rights`). Then the public surface of M5 still holds:
calendars, canary, Schemathesis, snapshot cache and the 20 sample searches.

Only for the local stack. Every person logs in through the real OIDC flow; SQL moves clocks
or seeds the canary and the synthetic search corpus. `--only=a,b` limits the items.
"""

from __future__ import annotations

import sys

import httpx

from scripts import dossier_api as dossier
from scripts import m4_ops as ops
from scripts.acceptance_common import PREFIX, check, expect, feed_items, login, step
from scripts.m5_live import anonymous, bump_feed
from scripts.m5_public import check_cache, check_canary, check_ics, check_schemathesis
from scripts.m5_search import check_search
from scripts.m5b_dossier import check_doc_path, check_template
from scripts.m5b_rights import check_gone, check_invalidation, check_rights

PREFIX[0] = "m5b"


def feed_ids() -> set[str]:
    """Return the ids of the public feed."""
    return {item["id"] for item in feed_items()}


def check_lifecycle(organizer: httpx.Client, editor: httpx.Client, viewer: httpx.Client) -> None:
    """Item a: draft, publish, hints, cancel, unpublish, archive, restore and the rights."""
    eid = dossier.create(organizer, "M5b Lebenslauf")
    event = expect(organizer.get(f"/api/events/{eid}"), 200, "a: read the draft")
    check(
        event["state"] == "draft" and "publish" in event["allowedActions"], "a: a draft can publish"
    )
    check(eid not in feed_ids(), "a: a draft is not public")
    expect(
        viewer.post(f"/api/events/{eid}/publish", headers=dossier.etag(organizer, eid)),
        403,
        "a: a viewer cannot publish",
    )
    done = dossier.act(organizer, eid, "publish")
    check(done["state"] == "published" and done["slug"], f"a: published as {done['slug']}")
    check(eid in feed_ids(), "a: the published dossier is in the feed without a poster")
    item = next(i for i in feed_items() if i["id"] == eid)
    check(item["image"] is None, "a: no poster -> image null")
    hints = expect(organizer.get(f"/api/events/{eid}/hints"), 200, "a: hints")["items"]
    codes = {h["code"] for h in hints}
    check("no_poster" in codes, f"a: the hint no_poster is there ({sorted(codes)})")
    dossier.act(organizer, eid, "cancel", reason="Saal belegt", publicReasonCode="room")
    gone = next(i for i in feed_items() if i["id"] == eid)
    check(gone["status"] == "cancelled", "a: cancel shows in the feed")
    dossier.act(organizer, eid, "reinstate")
    dossier.act(organizer, eid, "unpublish")
    check(eid not in feed_ids(), "a: unpublish takes it out of the feed")
    dossier.act(organizer, eid, "publish")
    dossier.act(organizer, eid, "archive")
    check(eid in feed_ids(), "a: the archive stays in the feed")
    locked = organizer.patch(
        f"/api/events/{eid}", json={"title": "Nein"}, headers=dossier.etag(organizer, eid)
    )
    check(locked.status_code == 409, "a: base data of the archive are locked")
    expect(
        organizer.post(
            f"/api/events/{eid}/documents", json={"kind": "retrospective", "bodyMd": "Gut."}
        ),
        201,
        "a: the retrospective is written in the archive",
    )
    expect(
        organizer.post(f"/api/events/{eid}/restore", headers=dossier.etag(organizer, eid)),
        403,
        "a: the organizer cannot restore",
    )
    back = dossier.act(editor, eid, "restore")
    check(
        back["state"] == "draft" and eid not in feed_ids(), "a: the editorial team restores a draft"
    )


def check_worker(organizer: httpx.Client) -> None:
    """Item b: the worker archives a published dossier twelve hours after its end."""
    eid = dossier.published(organizer, "M5b Worker")
    ops.query(
        "UPDATE event SET starts_at = starts_at - interval '40 days', "
        "ends_at = ends_at - interval '40 days' WHERE id = :e",
        e=eid,
    )
    ops.run_job("archive_ended")
    state = ops.query("SELECT state FROM event WHERE id = :e", e=eid)[0][0]
    check(state == "archived", f"b: the worker archived the ended dossier ({state})")
    actor = ops.query(
        "SELECT actor_type FROM event_status_event WHERE event_id = :e ORDER BY id DESC LIMIT 1",
        e=eid,
    )[0][0]
    check(actor == "system", "b: the status event names the system")
    bump_feed()


def main() -> None:
    """Run the M5b acceptance checks (`--only=a,b` limits the items)."""
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), "abcdefgh")
    ops.reset_upload_limits()
    organizer, editor = login("organizer-fsi"), login("editor")
    makers, member, viewer = login("organizer-makers"), login("member"), login("viewer-fsi")
    if "a" in only:
        check_doc_path(organizer)
        check_lifecycle(organizer, editor, viewer)
    if "b" in only:
        check_rights(organizer, editor, login("submitter-fsi"), makers)
        check_worker(organizer)
    if "c" in only:
        check_ics(organizer, editor)
    if "d" in only:
        check_canary(organizer, member, makers, viewer, dossier.archived(organizer, "M5b Canary"))
    if "e" in only:
        check_schemathesis()
    if "f" in only:
        check_gone(organizer)
        check_cache(organizer)
    if "g" in only:
        check_search()
        check_template(organizer, editor)
    if "h" in only:
        check_invalidation(organizer, editor)
        with anonymous() as client:
            expect(client.get("/api/public/feed/events"), 200, "h: the public feed answers")
    step("all checks passed")


if __name__ == "__main__":
    main()
