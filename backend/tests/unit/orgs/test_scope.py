"""Organization scope: binding, scoped id sets and the own-dossier rule."""

from __future__ import annotations

from uuid import uuid4

from app.modules.orgs import scope
from tests._support.auth_fakes import fake_session, result
from tests._support.factories import make_principal


async def test_bind_maps_slugs_with_one_query_and_is_idempotent() -> None:
    fsi, makers = uuid4(), uuid4()
    principal = make_principal("events-fsi-organizer", "events-makers-submitter")
    session = fake_session(result(("fsi", fsi), ("makers", makers)))
    await scope.bind(session, principal)
    assert principal.org_ids == {"fsi": str(fsi), "makers": str(makers)}
    await scope.bind(session, principal)
    await scope.bind(fake_session(), make_principal())


async def test_org_ids_for_is_none_for_a_global_right_else_the_role_orgs() -> None:
    fsi = uuid4()
    editor = make_principal("events-editor")
    assert await scope.org_ids_for(fake_session(), editor, "event.create") is None
    organizer = make_principal("events-fsi-organizer", "events-makers-viewer")
    ids = await scope.org_ids_for(
        fake_session(result(("fsi", fsi), ("makers", uuid4()))), organizer, "event.submit"
    )
    assert ids == {fsi}
    nobody = make_principal()
    assert await scope.org_ids_for(fake_session(), nobody, "event.create") == set()


async def test_readable_org_ids_cover_every_org_role_and_all_for_the_editor() -> None:
    fsi, makers = uuid4(), uuid4()
    assert await scope.readable_org_ids(fake_session(), make_principal("events-editor")) is None
    viewer = make_principal("events-fsi-viewer", "events-makers-submitter")
    ids = await scope.readable_org_ids(
        fake_session(result(("fsi", fsi), ("makers", makers))), viewer
    )
    assert ids == {fsi, makers}


def test_only_submitters_are_restricted_to_their_own_dossiers() -> None:
    org = uuid4()
    for group, restricted in [
        ("events-fsi-submitter", True),
        ("events-fsi-organizer", False),
        ("events-fsi-approver", False),
        ("events-editor", False),
    ]:
        principal = make_principal(group)
        principal.bind_org_ids({"fsi": org})
        assert scope.restricted_to_own(principal, org) is restricted
