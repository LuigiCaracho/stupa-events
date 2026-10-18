"""Four-Eyes (E06): the approving person did not submit, in the guard and in the database."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from app.settings import get_settings
from tests._support.factories import make_settings
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def stupa_in_review(api: Api, submitter: str = "approver-stupa") -> str:
    event = await api.create_event(user=submitter, org="stupa", title="STUPA Sitzung")
    eid = event["id"]
    assert (await api.fire(submitter, eid, "T01")).status_code == 200
    granted = await api.action("editor", eid, "image-exception", reason="Sitzung ohne Motiv")
    assert granted.status_code == 200
    assert (await api.fire(submitter, eid, "T02")).status_code == 200
    return eid


async def test_a_trusted_approver_cannot_approve_the_own_submission(api: Api) -> None:
    eid = await stupa_in_review(api)
    refused = await api.fire("approver-stupa", eid, "T04")
    assert refused.status_code == 403 and refused.json()["code"] == "four_eyes"
    assert refused.json()["reasons"][0]["code"] == "four_eyes"
    assert (await api.get("editor", eid))["state"] == "in_review"
    guards = (await api.request("approver-stupa", "GET", f"/api/events/{eid}/guards/T04")).json()
    assert guards["allowed"] is False and guards["reasons"][0]["code"] == "four_eyes"
    approved = await api.fire("approver2-stupa", eid, "T04")
    assert approved.status_code == 200 and approved.json()["approvedBy"] == "sub-app2-stupa"
    assert (await api.fire("approver-stupa", eid, "T05")).status_code == 200


async def test_the_editor_approves_the_own_submission_and_the_audit_says_so(api: Api) -> None:
    event = await api.to_state("planning", user="editor")
    await api.action("editor", event["id"], "image-exception", reason="Test ohne Motiv")
    assert (await api.fire("editor", event["id"], "T02")).status_code == 200
    assert (await api.fire("editor", event["id"], "T04")).status_code == 200
    rows = await api.sql(
        "SELECT data FROM audit_entry WHERE action = 'event_transition' ORDER BY id DESC LIMIT 1"
    )
    assert rows[0][0]["selfApproved"] is True and rows[0][0]["transition"] == "T04"


async def test_the_editor_is_bound_with_editor_four_eyes(api: Api) -> None:
    from app.settings import get_settings as real

    api.app.dependency_overrides[real] = lambda: make_settings(editor_four_eyes=True)
    event = await api.to_state("planning", user="editor")
    await api.action("editor", event["id"], "image-exception", reason="Test ohne Motiv")
    await api.fire("editor", event["id"], "T02")
    refused = await api.fire("editor", event["id"], "T04")
    assert refused.status_code == 403 and refused.json()["code"] == "four_eyes"
    assert (await api.fire("admin", event["id"], "T04")).status_code == 200
    assert get_settings().editor_four_eyes is False


async def test_the_admin_is_bound(api: Api) -> None:
    event = await api.create_event(user="admin")
    eid = event["id"]
    await api.fire("admin", eid, "T01")
    await api.action("admin", eid, "image-exception", reason="Test ohne Motiv")
    await api.fire("admin", eid, "T02")
    refused = await api.fire("admin", eid, "T04")
    assert refused.status_code == 403 and refused.json()["code"] == "four_eyes"
    assert (await api.fire("editor", eid, "T04")).status_code == 200


async def test_a_dossier_without_a_submitter_blocks_the_approver(api: Api) -> None:
    eid = await stupa_in_review(api)
    await api.sql("UPDATE event SET submitted_by = NULL WHERE id = :i", i=eid)
    refused = await api.fire("approver2-stupa", eid, "T04")
    assert refused.status_code == 403 and refused.json()["code"] == "four_eyes"


async def test_the_status_event_records_the_binding(api: Api) -> None:
    eid = await stupa_in_review(api)
    await api.fire("approver2-stupa", eid, "T04")
    rows = await api.sql(
        "SELECT four_eyes, submitted_by, actor_id FROM event_status_event "
        "WHERE event_id = :i AND transition_id = 'T04'",
        i=eid,
    )
    assert rows == [(True, "sub-app-stupa", "sub-app2-stupa")]


def test_the_database_refuses_a_self_approval_row(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO event (id, title, starts_at, ends_at, organization_id, created_by) "
                "SELECT '00000000-0000-0000-0000-0000000000bb', 'Roh', now() + interval '1 day', "
                "now() + interval '2 days', id, 'sql' FROM organization WHERE slug = 'fsi'"
            )
        )
    insert = (
        "INSERT INTO event_status_event (event_id, to_state, transition_id, actor_id, four_eyes, "
        "submitted_by) VALUES ('00000000-0000-0000-0000-0000000000bb', 'approved', :t, :a, :f, :s)"
    )
    with pytest.raises(DBAPIError) as caught, engine.begin() as conn:
        conn.execute(text(insert), {"t": "T04", "a": "x", "f": True, "s": "x"})
    assert getattr(caught.value.orig, "sqlstate", None) == "23514"
    assert "ck_event_status_event_four_eyes" in str(caught.value.orig)
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(text(insert), {"t": "T04", "a": "x", "f": True, "s": None})
    with engine.begin() as conn:
        conn.execute(text(insert), {"t": "T04", "a": "x", "f": True, "s": "y"})
        conn.execute(text(insert), {"t": "T04", "a": "x", "f": False, "s": "x"})
        conn.execute(text(insert), {"t": "T05", "a": "x", "f": True, "s": "x"})


async def test_the_database_net_answers_403_when_the_guard_is_bypassed(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    eid = await stupa_in_review(api)
    monkeypatch.setattr("app.modules.pipeline.decision.four_eyes", lambda *args: [])
    refused = await api.fire("approver-stupa", eid, "T04")
    assert refused.status_code == 403 and refused.json()["code"] == "four_eyes"
    assert (await api.get("editor", eid))["state"] == "in_review"
