"""`plan_patch`: the field classes, the lock table 3.2, all-or-nothing and `public_seq`."""

from __future__ import annotations

from datetime import timedelta
from itertools import product

import pytest

from app.modules.pipeline import fieldclass
from app.modules.pipeline.fieldclass import (
    API_NAMES,
    CRITICAL_FIELDS,
    TEXT_FIELDS,
    edit_right,
    editable_fields,
    link_hosts,
    lock_reason,
    plan_patch,
)
from tests.unit.pipeline.support import NOW, actor, snap

STATES = ("idea", "planning", "in_review", "approved", "live", "followup", "archived", "withdrawn")
ROLES = ("submitter", "organizer", "approver", "editor")
CRITICAL_CHANGE = {"title": "Neuer Titel"}
TEXT_CHANGE = {"description_md": "Anderer Text"}


def expected_locked(state: str, role: str, kind: str) -> bool:
    """The table of contract 3.2, written out per state and class."""
    if state in {"idea", "planning"}:
        return False
    if kind == "critical":
        return not (state == "live" and role in {"approver", "editor"})
    if state == "live":
        return False
    return not (state == "in_review" and role in {"approver", "editor"})


@pytest.mark.parametrize(
    ("state", "role", "kind"), list(product(STATES, ROLES, ("critical", "text")))
)
def test_lock_table(state: str, role: str, kind: str) -> None:
    change = CRITICAL_CHANGE if kind == "critical" else TEXT_CHANGE
    plan = plan_patch(snap(state=state), actor(role), change)
    assert bool(plan.locked) is expected_locked(state, role, kind)


def test_mixed_fields_lock_the_whole_request() -> None:
    plan = plan_patch(snap(state="live"), actor("organizer"), {**CRITICAL_CHANGE, "summary": "Neu"})
    assert plan.locked == ("title",)
    both = plan_patch(snap(state="approved"), actor("editor"), {"title": "x", "summary": "y"})
    assert set(both.locked) == {"title", "summary"}


def test_unchanged_values_are_ignored() -> None:
    snapshot = snap(state="live")
    plan = plan_patch(snapshot, actor("organizer"), {"title": snapshot.title, "summary": "Neu"})
    assert plan.locked == () and set(plan.changes) == {"summary"}


def test_classes_and_public_seq_in_live() -> None:
    live = snap(state="live")
    text = plan_patch(live, actor("organizer"), {"description_md": "x"})
    assert (text.field_class, text.bump_public_seq, text.live_guards) == ("text", False, False)
    summary = plan_patch(live, actor("organizer"), {"summary": "x"})
    assert (summary.field_class, summary.bump_public_seq) == ("text", True)
    critical = plan_patch(live, actor("editor"), {"starts_at": NOW + timedelta(days=9)})
    assert (critical.field_class, critical.bump_public_seq, critical.live_guards) == (
        "critical",
        True,
        True,
    )


def test_public_seq_never_moves_before_live() -> None:
    for state in ("idea", "planning", "in_review"):
        plan = plan_patch(snap(state=state), actor("editor"), {"title": "x", "summary": "y"})
        assert not plan.bump_public_seq and not plan.live_guards


def test_a_new_link_host_makes_text_critical() -> None:
    live = snap(state="live", description_md="Mehr unter https://example.org/info")
    known = plan_patch(
        live, actor("organizer"), {"description_md": "Siehe https://EXAMPLE.org/anders"}
    )
    assert known.locked == () and known.field_class == "text"
    fresh = plan_patch(live, actor("organizer"), {"description_md": "https://neu.example.net"})
    assert fresh.locked == ("descriptionMd",) and fresh.field_class == "critical"
    allowed = plan_patch(live, actor("editor"), {"description_md": "https://neu.example.net"})
    assert allowed.locked == () and allowed.bump_public_seq and allowed.live_guards


def test_links_are_critical_fields() -> None:
    plan = plan_patch(
        snap(state="live"), actor("organizer"), {"ticket_url": "https://tickets.example.org/x"}
    )
    assert plan.locked == ("ticketUrl",)


def test_link_hosts() -> None:
    text = "https://Example.ORG:8080/a, http://user@sub.example.org/x www.Beispiel.de mailto:a@b.de"
    assert link_hosts(text) == {"example.org", "sub.example.org", "www.beispiel.de"}
    assert link_hosts("https://bücher.example/x") == {"xn--bcher-kva.example"}
    assert link_hosts("https://" + "a" * 70 + ".de") == {"a" * 70 + ".de"}
    assert link_hosts(None) == frozenset() and link_hosts("kein Link") == frozenset()
    assert link_hosts("mail an me@www.example.org") == frozenset()
    assert link_hosts("https://.") == frozenset()


def test_known_hosts_cover_texts_and_urls() -> None:
    snapshot = snap(
        summary="https://a.example",
        description_md="https://b.example",
        cost_text="www.c.example",
        ticket_url="https://d.example/t",
        website_url="https://e.example",
    )
    assert fieldclass.known_hosts(snapshot) == {
        "a.example",
        "b.example",
        "www.c.example",
        "d.example",
        "e.example",
    }


def test_edit_right() -> None:
    assert edit_right(snap(state="idea", created_by="me"), actor("submitter", "me"))
    assert not edit_right(snap(state="idea", created_by="x"), actor("submitter", "me"))
    assert not edit_right(snap(state="in_review", created_by="me"), actor("submitter", "me"))
    assert not edit_right(snap(state="live", created_by="me"), actor("submitter", "me"))
    assert edit_right(snap(state="live"), actor("organizer"))
    assert not edit_right(snap(), actor("viewer"))
    assert not edit_right(snap(organization_id=None), actor("member"))
    assert edit_right(snap(organization_id=None), actor("editor"))


def test_lock_reason_and_editable_fields() -> None:
    assert lock_reason(snap(state="idea"), actor("organizer")) is None
    assert lock_reason(snap(state="in_review"), actor("approver")) == "in_review"
    assert lock_reason(snap(state="approved"), actor("editor")) == "approved"
    assert lock_reason(snap(state="live"), actor("organizer")) == "live_critical"
    assert lock_reason(snap(state="live"), actor("editor")) is None
    assert lock_reason(snap(state="archived"), actor("editor")) == "closed"
    open_fields = editable_fields(snap(state="planning"), actor("organizer"))
    assert set(open_fields) == {API_NAMES[n] for n in CRITICAL_FIELDS | TEXT_FIELDS}
    assert editable_fields(snap(state="live"), actor("organizer")) == sorted(
        API_NAMES[n] for n in TEXT_FIELDS
    ) or set(editable_fields(snap(state="live"), actor("organizer"))) == {
        API_NAMES[n] for n in TEXT_FIELDS
    }
    assert editable_fields(snap(state="live"), actor("viewer")) == []
    assert editable_fields(snap(state="in_review"), actor("organizer")) == []
    review = editable_fields(snap(state="in_review"), actor("approver"))
    assert set(review) == {API_NAMES[n] for n in TEXT_FIELDS}


@pytest.mark.parametrize(
    ("text", "hosts"),
    [
        ("[x](//evil.example/a)", {"evil.example"}),
        ("<a href='//evil.example'>x</a>", {"evil.example"}),
        ("ftp://files.example/a", {"files.example"}),
        ("siehe evil.example.", {"evil.example"}),
        ("evil.example/pfad?x=1", {"evil.example"}),
        ("https://trusted.example:x@evil.example/", {"evil.example"}),
        ("www.a.example, https://b.example:8080/x", {"www.a.example", "b.example"}),
        ("z.B. heute, um 18.30 Uhr, v1.2", set()),
        ("mail me@evil.example", set()),
    ],
)
def test_link_hosts_sees_every_target_with_an_authority(text: str, hosts: set[str]) -> None:
    assert link_hosts(text) == hosts


def test_a_live_summary_change_runs_the_live_guards() -> None:
    live = snap(state="live")
    plan = plan_patch(live, actor("organizer"), {"summary": None})
    assert plan.live_guards and plan.field_class == "text"
    assert not plan_patch(live, actor("organizer"), {"cost_text": "5 Euro"}).live_guards
