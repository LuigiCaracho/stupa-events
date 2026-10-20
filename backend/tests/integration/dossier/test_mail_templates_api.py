"""Mail templates: catalog placeholders only, rendered in local time, never sent."""

from __future__ import annotations

import pytest

from tests.integration.dossier.helpers import planning_event
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration

BODY = "Hallo, {{ event.title }} startet am {{ event.starts_local }} in {{ venue.name }} ({{ org.name }})."


async def save(api: Api, eid: str, doc: str = "new", user: str = "organizer-fsi", **over: object):  # noqa: ANN201
    body = {"title": "Einladung", "subject": "Einladung: {{ event.title }}", "bodyMd": BODY, **over}
    headers = {"If-Match": over.pop("ifMatch")} if "ifMatch" in over else {}  # type: ignore[arg-type]
    return await api.request(
        user, "PUT", f"/api/events/{eid}/mail-templates/{doc}", json=body, headers=headers
    )


async def test_create_list_render_and_save_again(api: Api) -> None:
    eid = await planning_event(api, venueText="Kinosaal 9-133")
    created = await save(api, eid)
    assert created.status_code == 201, created.text
    tpl = created.json()
    assert created.headers["etag"] == '"1"' and tpl["visibility"] == "shared"
    assert tpl["placeholders"] == ["event.starts_local", "event.title", "org.name", "venue.name"]
    listed = (await api.request("viewer-fsi", "GET", f"/api/events/{eid}/mail-templates")).json()
    assert [(t["title"], t["subject"]) for t in listed] == [
        ("Einladung", "Einladung: {{ event.title }}")
    ]
    got = await api.request("viewer-fsi", "GET", f"/api/events/{eid}/mail-templates/{tpl['id']}")
    assert got.json()["bodyMd"] == BODY
    url = f"/api/events/{eid}/mail-templates/{tpl['id']}/render-preview"
    event = await api.get("organizer-fsi", eid)
    rendered = (await api.request("organizer-fsi", "POST", url, json={})).json()
    assert rendered["subject"] == f"Einladung: {event['title']}"
    assert "Kinosaal 9-133" in rendered["body"] and "Uhr" in rendered["body"]
    assert "Fachschaft" in rendered["body"] or "FSI" in rendered["body"].upper()
    draft = await api.request(
        "organizer-fsi",
        "POST",
        url,
        json={"subject": "X {{ event.title }}", "bodyMd": "Nur {{ org.name }}"},
    )
    assert draft.json()["subject"].startswith("X ")
    updated = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/events/{eid}/mail-templates/{tpl['id']}",
        json={"subject": "Neu", "bodyMd": BODY, "toHint": "alle"},
        headers={"If-Match": '"1"'},
    )
    assert updated.status_code == 200 and updated.headers["etag"] == '"2"'
    assert updated.json()["toHint"] == "alle"
    stale = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/events/{eid}/mail-templates/{tpl['id']}",
        json={"subject": "Neu2", "bodyMd": BODY},
        headers={"If-Match": '"1"'},
    )
    assert stale.status_code == 409
    assert not api.pool.jobs or all(job[0] != "send_mail" for job in api.pool.jobs)


async def test_a_venue_less_dossier_renders_an_empty_venue(api: Api) -> None:
    eid = await planning_event(api, venueText="")
    tpl = (await save(api, eid, bodyMd="Ort: [{{ venue.name }}]")).json()
    url = f"/api/events/{eid}/mail-templates/{tpl['id']}/render-preview"
    assert (await api.request("organizer-fsi", "POST", url, json={})).json()["body"] == "Ort: []"


async def test_unknown_placeholders_statements_and_subject_lines_are_422(api: Api) -> None:
    eid = await planning_event(api)
    unknown = await save(api, eid, bodyMd="{{ event.raum }}")
    assert unknown.status_code == 422 and unknown.json()["code"] == "template_invalid"
    reason = unknown.json()["reasons"][0]
    assert reason["code"] == "unknown_placeholder" and reason["field"] == "event.raum"
    assert "event.title" in reason["allowed"]
    for body in (
        "{% if x %}a{% endif %}",
        "{{ event.title|upper }}",
        "{{ event.title.__class__ }}",
        "{{ 1 }}",
        "{{",
    ):
        response = await save(api, eid, bodyMd=body)
        assert response.status_code == 422, body
    newline = await save(api, eid, subject="a\nb")
    assert newline.status_code == 422 and newline.json()["code"] == "subject_newline"
    assert (await api.sql("SELECT count(*) FROM document"))[0][0] == 0


async def test_rights_and_the_catalog(api: Api) -> None:
    eid = await planning_event(api)
    assert (await save(api, eid, user="viewer-fsi")).status_code == 403
    assert (await save(api, eid, user="organizer-makers")).status_code == 404
    tpl = (await save(api, eid)).json()
    other = await api.request(
        "organizer-fsi",
        "GET",
        f"/api/events/{await planning_event(api)}/mail-templates/{tpl['id']}",
    )
    assert other.status_code == 404
    catalog = (await api.request("viewer-fsi", "GET", "/api/mail-template-placeholders")).json()
    assert [c["path"] for c in catalog] == [
        "event.title",
        "event.starts_local",
        "venue.name",
        "org.name",
    ]
    assert (await api.request(None, "GET", "/api/mail-template-placeholders")).status_code == 401
    bad = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/events/{eid}/mail-templates/nope",
        json={"subject": "x", "bodyMd": "y"},
        headers={"If-Match": '"1"'},
    )
    assert bad.status_code == 404


async def test_an_unsaved_template_previews_under_new(api: Api) -> None:
    eid = await planning_event(api, venueText="Kinosaal 9-133")
    url = f"/api/events/{eid}/mail-templates/new/render-preview"
    draft = {"subject": "Hallo {{ event.title }}", "bodyMd": "Im {{ venue.name }}"}
    rendered = await api.request("organizer-fsi", "POST", url, json=draft)
    assert rendered.status_code == 200 and rendered.json()["body"] == "Im Kinosaal 9-133"
    empty = await api.request("organizer-fsi", "POST", url, json={})
    assert empty.status_code == 200 and empty.json() == {"subject": "", "body": ""}
    bad = await api.request("organizer-fsi", "POST", url, json={"bodyMd": "{{ event.raum }}"})
    assert bad.status_code == 422 and bad.json()["code"] == "template_invalid"
    other = f"/api/events/{eid}/mail-templates/not-a-uuid/render-preview"
    assert (await api.request("organizer-fsi", "POST", other, json={})).status_code == 404
    assert (await api.request("organizer-makers", "POST", url, json=draft)).status_code == 404
