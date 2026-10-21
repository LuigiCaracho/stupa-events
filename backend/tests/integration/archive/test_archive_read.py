"""Reading archived dossiers of other organizations: core data, shared documents and files."""

from __future__ import annotations

import pytest

from tests._support import samples
from tests.integration.archive.fixture import archived_movienight, ok
from tests.integration.dossier.helpers import upload
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


FILES = (("other", "shared", True), ("other", "org", True))


async def file_ids(api: Api, eid: str) -> dict[str, str]:
    """Return the ids of the extra files by name: clean, private, and a shared pending one."""
    await api.sql(
        "INSERT INTO attachment (event_id, display_name, storage_name, mime, size_bytes, sha256, "
        "scan_status, visibility, kind) VALUES (:e, 'wartet.pdf', 'w', 'application/pdf', 1, 'cc', "
        "'pending', 'shared', 'other')",
        e=eid,
    )
    rows = await api.sql(
        "SELECT id, visibility, scan_status FROM attachment WHERE event_id = :e AND kind = 'other'",
        e=eid,
    )
    names = {
        ("shared", "clean"): "clean",
        ("shared", "pending"): "pending",
        ("org", "clean"): "private",
    }
    return {names[(visibility, scan)]: str(i) for i, visibility, scan in rows}


async def test_the_archive_view_of_a_foreign_dossier_shows_core_data_and_shared_parts_only(
    api: Api,
) -> None:
    eid = await archived_movienight(api, files=FILES)
    clean = (await file_ids(api, eid))["clean"]
    foreign = await ok(await api.request("organizer-makers", "GET", f"/api/archive/{eid}"))
    assert foreign["own"] is False and foreign["attendance"] == 87
    assert foreign["title"] == "Movienight: Whiplash" and foreign["state"] == "archived"
    assert foreign["format"]["slug"] == "movienight"
    assert foreign["venueName"] == "Kinosaal 9-133"
    assert {d["kind"] for d in foreign["documents"]} == {"howto", "mail_template"}
    assert [a["id"] for a in foreign["attachments"]] == [clean]
    blob = str(foreign)
    for secret in ("24500", "13000", "Mehr Stühle", "Hausmeister", "Licht GmbH", "Saal war voll"):
        assert secret not in blob
    own = await ok(await api.request("organizer-fsi", "GET", f"/api/archive/{eid}"))
    assert own["own"] is True and {"notes", "retrospective"} <= {
        d["kind"] for d in own["documents"]
    }
    assert len(own["attachments"]) == 4  # poster, three files
    member = await api.request("member", "GET", f"/api/archive/{eid}")
    assert member.status_code == 200 and member.json()["own"] is False


async def test_a_private_venue_and_a_confirmed_text_in_the_archive_view(api: Api) -> None:
    eid = await archived_movienight(api)
    await api.sql("UPDATE event SET location_precision = 'building' WHERE id = :e", e=eid)
    shown = await ok(await api.request("member", "GET", f"/api/archive/{eid}"))
    assert shown["venueName"] == "Kinosaal 9-133"
    venue = await api.sql("SELECT id, name FROM venue WHERE is_private LIMIT 1")
    if not venue:
        await api.sql(
            "INSERT INTO venue (slug, name, is_private) VALUES ('privat', 'Bei Ada', true)"
        )
        venue = await api.sql("SELECT id, name FROM venue WHERE is_private LIMIT 1")
    await api.sql("UPDATE event SET venue_id = :v WHERE id = :e", v=venue[0][0], e=eid)
    private = await ok(await api.request("member", "GET", f"/api/archive/{eid}"))
    assert private["venueName"] is None
    mine = await ok(await api.request("organizer-fsi", "GET", f"/api/archive/{eid}"))
    assert mine["venueName"] == venue[0][1]


async def test_only_archived_foreign_dossiers_are_readable(api: Api) -> None:
    live = await api.to_state("live")
    assert (
        await api.request("organizer-makers", "GET", f"/api/archive/{live['id']}")
    ).status_code == 404
    assert (
        await api.request("organizer-fsi", "GET", f"/api/archive/{live['id']}")
    ).status_code == 200
    unknown = await api.request(
        "editor", "GET", "/api/archive/00000000-0000-0000-0000-000000000000"
    )
    assert unknown.status_code == 404
    assert (await api.request(None, "GET", f"/api/archive/{live['id']}")).status_code == 401


async def test_documents_of_a_foreign_archived_dossier(api: Api) -> None:
    eid = await archived_movienight(api)
    rows = await api.sql("SELECT id, kind, visibility FROM document WHERE event_id = :e", e=eid)
    by_kind = {kind: (str(i), visibility) for i, kind, visibility in rows}
    shared = by_kind["howto"][0]
    seen = await api.request("organizer-makers", "GET", f"/api/documents/{shared}")
    assert seen.status_code == 200 and seen.json()["bodyMd"].startswith("# Aufbau")
    assert (
        await api.request("organizer-makers", "GET", f"/api/documents/{by_kind['notes'][0]}")
    ).status_code == 404
    await api.sql(
        "UPDATE document SET visibility = 'team' WHERE id = :i", i=by_kind["mail_template"][0]
    )
    team = await api.request(
        "organizer-makers", "GET", f"/api/documents/{by_kind['mail_template'][0]}"
    )
    assert team.status_code == 404
    write = await api.request(
        "organizer-fsi" if False else "organizer-makers",
        "PUT",
        f"/api/documents/{shared}",
        json={"bodyMd": "x"},
        headers={"If-Match": '"1"'},
    )
    assert write.status_code == 404
    live = await api.to_state("live")
    await api.sql(
        "INSERT INTO document (event_id, kind, title, body_md, visibility) VALUES (:e, 'notes', 'n', 'b', 'shared')",
        e=live["id"],
    )
    row = await api.sql("SELECT id FROM document WHERE event_id = :e", e=live["id"])
    hidden = await api.request("organizer-makers", "GET", f"/api/documents/{row[0][0]}")
    assert hidden.status_code == 404


async def test_attachment_download_of_a_foreign_shared_file(api: Api) -> None:
    eid = await archived_movienight(api, files=FILES)
    ids = await file_ids(api, eid)
    shared, private, pending = ids["clean"], ids["private"], ids["pending"]
    got = await api.request("organizer-makers", "GET", f"/api/attachments/{shared}/download")
    assert got.status_code == 200 and got.content == samples.pdf_bytes()
    assert (
        await api.request("organizer-makers", "GET", f"/api/attachments/{private}/download")
    ).status_code == 404
    assert (
        await api.request("organizer-makers", "GET", f"/api/attachments/{pending}/download")
    ).status_code == 404
    assert (
        await api.request("organizer-fsi", "GET", f"/api/attachments/{pending}/download")
    ).status_code == 409
    retire = await api.request("organizer-makers", "POST", f"/api/attachments/{shared}/retire")
    assert retire.status_code == 404
    patch = await api.request(
        "organizer-makers", "PATCH", f"/api/attachments/{shared}", json={"visibility": "org"}
    )
    assert patch.status_code == 404
    await api.sql("UPDATE attachment SET retired_at = now() WHERE id = :a", a=shared)
    assert (
        await api.request("organizer-makers", "GET", f"/api/attachments/{shared}/download")
    ).status_code == 404
    live = await api.to_state("live")
    out = await upload(
        api, "organizer-fsi", live["id"], "other", "p.pdf", samples.pdf_bytes(), visibility="shared"
    )
    await api.process_poster(out.json()["id"])
    live_file = out.json()["id"]
    assert (
        await api.request("organizer-makers", "GET", f"/api/attachments/{live_file}/download")
    ).status_code == 404


async def test_the_quote_files_stay_private_even_in_the_archive(api: Api) -> None:
    eid = await archived_movienight(api, files=(("quote", "org", True),))
    view = await ok(await api.request("member", "GET", f"/api/archive/{eid}"))
    assert all(a["kind"] != "quote" for a in view["attachments"])
