"""Comments: anchors, resolving and the guards they feed (T03, T04)."""

from __future__ import annotations

import pytest

from tests._support import samples
from tests._support.factories import png_bytes
from tests.integration.dossier.helpers import draft_event, published_event, seed_principals, upload
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def comment(api: Api, eid: str, user: str = "editor", **over: object):  # noqa: ANN201
    body = {"bodyMd": "Bitte prüfen", **over}
    return await api.request(user, "POST", f"/api/events/{eid}/comments", json=body)


async def test_anchor_validation(api: Api) -> None:
    eid = await draft_event(api)
    other = await draft_event(api)
    doc = (
        await api.request(
            "organizer-fsi",
            "POST",
            f"/api/events/{eid}/documents",
            json={"kind": "notes", "title": "N", "bodyMd": "abcdefghij"},
        )
    ).json()
    mine = (await upload(api, "organizer-fsi", eid, "other", "a.png", png_bytes())).json()
    foreign = (await upload(api, "organizer-fsi", other, "other", "b.png", png_bytes())).json()
    item = (
        await api.request(
            "organizer-fsi",
            "POST",
            f"/api/events/{eid}/checklist/items",
            json={"text": "Punkt", "phase": "live"},
        )
    ).json()
    good = [
        {"field": "hero"},
        {"field": "title"},
        {"attachmentId": mine["id"]},
        {"checklistItemId": item["id"]},
        {"documentId": doc["id"], "rev": 1, "from": 2, "to": 5},
    ]
    bad = [
        {"field": "bogus"},
        {"field": "hero", "attachmentId": mine["id"]},
        {"attachmentId": foreign["id"]},
        {"attachmentId": "nope"},
        {"checklistItemId": "00000000-0000-0000-0000-000000000000"},
        {"documentId": doc["id"], "rev": 1, "from": 5, "to": 5},
        {"documentId": doc["id"], "rev": 1, "from": 0, "to": 99},
        {"documentId": doc["id"], "rev": 7, "from": 0, "to": 1},
        {"documentId": doc["id"], "from": 0, "to": 1},
        {},
    ]
    for anchor in good:
        assert (await comment(api, eid, anchor=anchor)).status_code == 201, anchor
    for anchor in bad:
        response = await comment(api, eid, anchor=anchor)
        assert response.status_code == 422 and response.json()["code"] == "anchor_invalid", anchor
    assert (await comment(api, eid, anchor=None)).status_code == 201


async def test_replies_resolve_and_reopen(api: Api) -> None:
    await seed_principals(api)
    eid = await draft_event(api)
    root = (await comment(api, eid, user="organizer-fsi", anchor={"field": "title"})).json()
    reply = await comment(api, eid, user="editor", parentId=root["id"])
    assert reply.status_code == 201 and reply.json()["anchor"] is None
    with_anchor = await comment(api, eid, parentId=root["id"], anchor={"field": "title"})
    assert with_anchor.status_code == 422
    nested = await comment(api, eid, parentId=reply.json()["id"])
    assert nested.status_code == 422
    threads = (await api.request("viewer-fsi", "GET", f"/api/events/{eid}/comments")).json()
    assert len(threads) == 1 and len(threads[0]["replies"]) == 1
    assert threads[0]["authorName"] == "Organizer Fsi"
    assert (await comment(api, eid, user="viewer-fsi")).status_code == 403
    assert (await comment(api, eid, user="organizer-makers")).status_code == 404
    url = f"/api/comments/{root['id']}"
    other_organizer = await api.request("submitter-fsi", "POST", f"{url}/resolve")
    assert other_organizer.status_code == 403
    done = await api.request("editor", "POST", f"{url}/resolve")
    assert done.status_code == 200 and done.json()["resolvedBy"] == "sub-editor"
    again = await api.request("editor", "POST", f"{url}/resolve")
    assert again.json()["resolvedAt"] == done.json()["resolvedAt"]
    open_only = (await api.request("editor", "GET", f"/api/events/{eid}/comments?open=true")).json()
    assert open_only == []
    reopened = await api.request("organizer-fsi", "POST", f"{url}/reopen")
    assert reopened.status_code == 200 and reopened.json()["resolvedAt"] is None
    not_root = await api.request("editor", "POST", f"/api/comments/{reply.json()['id']}/resolve")
    assert not_root.status_code == 409 and not_root.json()["code"] == "not_a_root"
    kinds = [r[0] for r in await api.sql("SELECT kind FROM notification ORDER BY created_at")]
    assert kinds.count("comment_added") >= 1 and "comment_resolved" not in kinds


async def test_comments_are_append_only_in_the_database(api: Api) -> None:
    eid = await draft_event(api)
    made = (await comment(api, eid)).json()
    with pytest.raises(Exception, match="append-only"):
        await api.sql("UPDATE comment SET body_md = 'x' WHERE id = :i", i=made["id"])
    with pytest.raises(Exception, match="append-only"):
        await api.sql("DELETE FROM comment WHERE id = :i", i=made["id"])
    await api.sql("UPDATE comment SET resolved_by = 'x' WHERE id = :i", i=made["id"])


async def test_open_comments_never_block_publishing(api: Api) -> None:
    eid = await draft_event(api)
    await comment(api, eid, anchor={"field": "hero"})
    assert (await api.act("organizer-fsi", eid, "publish")).status_code == 200


async def test_a_question_on_a_poster_file_survives_the_replacement(api: Api) -> None:
    event = await published_event(api)
    eid, first = event["id"], event["poster"]["id"]
    made = await comment(api, eid, anchor={"attachmentId": first})
    assert made.status_code == 201
    fresh = (await api.upload_poster("editor", eid, data=png_bytes(1400, 900))).json()
    assert await api.process_poster(fresh["id"]) == "clean"
    threads = (await api.request("editor", "GET", f"/api/events/{eid}/comments")).json()
    assert [t["anchor"]["attachmentId"] for t in threads] == [first]


async def test_publishing_and_comments_notify_the_right_people(api: Api) -> None:
    await seed_principals(api)
    event = await api.create_event()
    await api.act("organizer-fsi", event["id"], "publish")
    rows = [tuple(r) for r in await api.sql("SELECT recipient_sub, kind FROM notification")]
    assert ("sub-editor", "published") in rows
    assert all(sub != "sub-org-fsi" for sub, kind in rows if kind == "published")


async def test_a_pdf_in_a_comment_anchor_is_not_a_poster_target(api: Api) -> None:
    eid = await draft_event(api)
    pdf = (await upload(api, "organizer-fsi", eid, "other", "a.pdf", samples.pdf_bytes())).json()
    assert (await comment(api, eid, anchor={"attachmentId": pdf["id"]})).status_code == 201
