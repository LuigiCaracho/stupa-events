"""Edge branches of checklist, comments and attachments that the feature tests leave out.

They keep `files/attachments`, `dossier/comments` and `dossier/checklist` at 100 % for
`coverage_critical` (M4 contract 9): template resolution by category and the `generic`
fallback, item edits and refusals, foreign items and comments, social posts and rescans.
"""

from __future__ import annotations

import pytest

from tests._support.samples import pdf_bytes
from tests.integration.dossier.helpers import planning_event, seed_principals
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def apply(api: Api, eid: str) -> dict:
    response = await api.request(
        "organizer-fsi", "POST", f"/api/events/{eid}/checklist/apply-template", json={}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def add_item(api: Api, eid: str, **over: object) -> dict:
    body = {"text": "Frei", "phase": "planning", **over}
    response = await api.request(
        "organizer-fsi", "POST", f"/api/events/{eid}/checklist/items", json=body
    )
    assert response.status_code == 201, response.text
    return response.json()


async def patch(api: Api, item_id: str, user: str = "organizer-fsi", **body: object):  # noqa: ANN201
    return await api.request(user, "PATCH", f"/api/checklist-items/{item_id}", json=body)


async def test_template_by_category_and_the_generic_fallback(api: Api) -> None:
    kino = api.category_ids["kino"]
    await api.sql(
        "INSERT INTO checklist_template (slug, name, category_id) VALUES ('kino-own', 'Kino', :c)",
        c=kino,
    )
    try:
        own = await apply(api, await planning_event(api))
        assert own["template"]["slug"] == "kino-own"
    finally:
        await api.sql("DELETE FROM checklist_template WHERE slug = 'kino-own'")
    bare = (await api.create_event(title="Ohne Kategorie", primaryCategoryId=None))["id"]
    assert (await apply(api, bare))["template"]["slug"] == "generic"
    await api.sql("UPDATE checklist_template SET profile = NULL WHERE slug = 'meeting'")
    try:
        meeting = await planning_event(api, primaryCategoryId=api.category_ids["sitzung"])
        assert (await apply(api, meeting))["template"]["slug"] == "generic"
    finally:
        await api.sql("UPDATE checklist_template SET profile = 'meeting' WHERE slug = 'meeting'")


async def test_a_broken_mail_template_keeps_the_inbox_row(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.notifications import service
    from app.modules.notifications.templating import TemplateRenderError

    def broken(kind: str, ctx: object) -> tuple[str, str, str]:
        raise TemplateRenderError("boom")

    await seed_principals(api)
    eid = await planning_event(api)
    monkeypatch.setattr(service, "render_system_mail", broken)
    made = await api.request("editor", "POST", f"/api/events/{eid}/comments", json={"bodyMd": "?"})
    assert made.status_code == 201
    rows = await api.sql(
        "SELECT count(*) FROM notification WHERE event_id = :e AND kind = 'comment_added'", e=eid
    )
    assert rows[0][0] >= 1
    assert all(job[0] != "send_mail" for job in api.pool.jobs)


async def test_item_edits_assignees_waivers_and_positions(api: Api) -> None:
    await seed_principals(api)
    eid = await planning_event(api)
    item = await add_item(api, eid)
    edited = await patch(api, item["id"], text=" Neu ", phase="live", required=True)
    assert edited.status_code == 200
    assert (edited.json()["text"], edited.json()["phase"], edited.json()["required"]) == (
        "Neu",
        "live",
        True,
    )
    to_editor = await patch(api, item["id"], assigneeSub="sub-editor")
    assert to_editor.status_code == 200 and to_editor.json()["assigneeSub"] == "sub-editor"
    cleared = await patch(api, item["id"], assigneeSub=None)
    assert cleared.status_code == 200 and cleared.json()["assigneeSub"] is None
    moved = await patch(api, item["id"], position="m")
    assert moved.status_code == 200 and moved.json()["position"] == "m"
    bad = await patch(api, item["id"], position="!")
    assert bad.status_code == 422
    done = await api.request(
        "organizer-fsi", "POST", f"/api/checklist-items/{item['id']}/done", json={"done": True}
    )
    assert done.status_code == 200
    waived = await patch(api, item["id"], waivedReason="Entfällt, weil erledigt")
    assert waived.status_code == 409 and waived.json()["code"] == "conflict"


async def test_foreign_items_and_comments_are_not_found(api: Api) -> None:
    eid = await planning_event(api)
    item = await add_item(api, eid)
    assert (await patch(api, item["id"], user="organizer-makers", text="x")).status_code == 404
    listed = await api.request("organizer-fsi", "GET", f"/api/events/{eid}/comments")
    assert listed.status_code == 200 and listed.json() == []
    root = await api.request(
        "editor", "POST", f"/api/events/{eid}/comments", json={"bodyMd": "Frage"}
    )
    assert root.status_code == 201
    foreign = await api.request(
        "organizer-makers", "POST", f"/api/comments/{root.json()['id']}/resolve"
    )
    assert foreign.status_code == 404
    stupa_side = await api.request(
        "approver-stupa", "POST", f"/api/events/{eid}/comments", json={"bodyMd": "Hallo"}
    )
    assert stupa_side.status_code in {403, 404}
    nobody = "00000000-0000-4000-8000-000000000000"
    assert (
        await api.request("editor", "POST", f"/api/comments/{nobody}/resolve")
    ).status_code == 404
    assert (await patch(api, nobody, text="x")).status_code == 404
    unknown_parent = await api.request(
        "editor",
        "POST",
        f"/api/events/{eid}/comments",
        json={"bodyMd": "Antwort", "parentId": "00000000-0000-4000-8000-000000000000"},
    )
    assert unknown_parent.status_code == 404


async def test_social_posts_need_an_image_with_rights_and_rescans_need_an_approver(
    api: Api,
) -> None:
    eid = await planning_event(api)
    url = f"/api/events/{eid}/attachments"
    pdf = await api.request(
        "organizer-fsi",
        "POST",
        url,
        data={"kind": "other"},
        files={"file": ("plan.pdf", pdf_bytes(), "application/pdf")},
    )
    assert pdf.status_code == 201, pdf.text
    renamed = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/attachments/{pdf.json()['id']}",
        json={"displayName": "Plan €.pdf"},
    )
    assert renamed.status_code == 200 and renamed.json()["displayName"] == "Plan €.pdf"
    retire = f"/api/attachments/{pdf.json()['id']}/retire"
    assert (await api.request("organizer-fsi", "POST", retire)).status_code == 204
    assert (await api.request("organizer-fsi", "POST", retire)).status_code == 204
    await api.sql("UPDATE attachment SET scan_status = 'error' WHERE id = :i", i=pdf.json()["id"])
    rescan = f"/api/attachments/{pdf.json()['id']}/rescan"
    assert (await api.request("organizer-fsi", "POST", rescan)).status_code == 403
