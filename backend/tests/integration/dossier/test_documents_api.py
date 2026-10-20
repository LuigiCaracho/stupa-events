"""Documents: ETag discipline, append-only revisions, diff, autosave and verbatim storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._support.factories import png_bytes
from tests.integration.dossier.helpers import planning_event
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration

CORPUS_DIR = Path(__file__).resolve().parents[4] / "frontend" / "tests" / "fixtures" / "markdown"
INLINE_CORPUS = [
    "# Titel\n\nText mit Umlauten äöüß und €.\n",
    "- a\n  - b\n    - c\n\n1. eins\n2. zwei\n",
    "| a | b |\n|:--|--:|\n| 1 | 2 |\n",
    "Hallo 👨‍👩‍👧 Welt\n\n\n",
    "ohne Zeilenende",
    "Zeile eins\r\nZeile zwei\r\n",
    "Hallo {{ event.title }} am {{ event.starts_local }}\n",
    "```python\nprint('x')\n```\n\n> Zitat\n\n[Link](https://example.org) ~~weg~~ **fett** *kursiv*\n",
]


async def create_doc(api: Api, eid: str, user: str = "organizer-fsi", **over: object):  # noqa: ANN201
    body = {"kind": "howto", "title": "Ablauf", "bodyMd": "# Eins\n\nzwei\n", **over}
    return await api.request(user, "POST", f"/api/events/{eid}/documents", json=body)


async def test_create_read_and_the_single_howto(api: Api) -> None:
    eid = await planning_event(api)
    created = await create_doc(api, eid)
    assert created.status_code == 201 and created.headers["etag"] == '"1"'
    doc = created.json()
    assert doc["rev"] == 1 and doc["visibility"] == "shared" and doc["carryOver"] is True
    again = await create_doc(api, eid)
    assert again.status_code == 409 and again.json()["code"] == "already_exists"
    note = await create_doc(api, eid, kind="notes", title="Notiz")
    assert note.status_code == 201 and note.json()["visibility"] == "org"
    got = await api.request("organizer-fsi", "GET", f"/api/documents/{doc['id']}")
    assert got.status_code == 200 and got.json()["bodyMd"] == "# Eins\n\nzwei\n"
    listed = (await api.request("viewer-fsi", "GET", f"/api/events/{eid}/documents")).json()
    assert sorted(d["kind"] for d in listed) == ["howto", "notes"]
    assert "bodyMd" not in listed[0]


async def test_put_needs_if_match_conflicts_with_current_and_noops(api: Api) -> None:
    eid = await planning_event(api)
    doc = (await create_doc(api, eid)).json()
    url = f"/api/documents/{doc['id']}"
    body = {"bodyMd": "# Eins\n\nzwei\ndrei\n", "changeNote": "drei"}
    assert (await api.request("organizer-fsi", "PUT", url, json=body)).status_code == 428
    star = await api.request("organizer-fsi", "PUT", url, json=body, headers={"If-Match": "*"})
    assert star.status_code == 428
    saved = await api.request("organizer-fsi", "PUT", url, json=body, headers={"If-Match": '"1"'})
    assert saved.status_code == 200 and saved.headers["etag"] == '"2"'
    stale = await api.request("organizer-fsi", "PUT", url, json=body, headers={"If-Match": '"1"'})
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"
    assert stale.json()["current"]["rev"] == 2
    noop = await api.request("organizer-fsi", "PUT", url, json=body, headers={"If-Match": '"2"'})
    assert noop.status_code == 200 and noop.headers["etag"] == '"2"'
    assert (await api.sql("SELECT count(*) FROM document_revision"))[0][0] == 2
    cannot = await api.request("viewer-fsi", "PUT", url, json=body, headers={"If-Match": '"2"'})
    assert cannot.status_code == 403
    foreign = await api.request("organizer-makers", "GET", url)
    assert foreign.status_code == 404


async def test_revisions_are_append_only_and_diffable(api: Api) -> None:
    eid = await planning_event(api)
    doc = (await create_doc(api, eid)).json()
    url = f"/api/documents/{doc['id']}"
    await api.request(
        "organizer-fsi",
        "PUT",
        url,
        json={"title": "Neuer Titel", "bodyMd": "# Eins\n\nzwei\ndrei\n", "changeNote": "drei"},
        headers={"If-Match": '"1"'},
    )
    history = (await api.request("organizer-fsi", "GET", f"{url}/revisions")).json()
    assert [h["rev"] for h in history] == [2, 1]
    assert history[0]["titleChanged"] is True and history[0]["charsDelta"] == 5
    assert history[0]["changeNote"] == "drei"
    full = (await api.request("organizer-fsi", "GET", f"{url}/revisions/1")).json()
    assert full["bodyMd"] == "# Eins\n\nzwei\n" and full["title"] == "Ablauf"
    assert (await api.request("organizer-fsi", "GET", f"{url}/revisions/9")).status_code == 404
    diff = (await api.request("organizer-fsi", "GET", f"{url}/diff?from=1&to=2")).json()
    assert diff["added"] == 1 and diff["removed"] == 0
    assert [(ln["op"], ln["text"]) for ln in diff["lines"]][-1] == ("add", "drei")
    for statement in (
        "UPDATE document_revision SET body_md = 'x'",
        "DELETE FROM document_revision",
        "TRUNCATE document_revision",
    ):
        with pytest.raises(Exception, match="append-only|permission denied"):
            await api.sql(statement)


async def test_autosave_keeps_a_draft_without_a_revision(api: Api) -> None:
    eid = await planning_event(api)
    doc = (await create_doc(api, eid)).json()
    url = f"/api/documents/{doc['id']}/draft"
    assert (await api.request("organizer-fsi", "GET", url)).status_code == 204
    put = await api.request(
        "organizer-fsi", "PUT", url, json={"bodyMd": "Entwurf"}, headers={"If-Match": '"1"'}
    )
    assert put.status_code == 200 and put.json()["baseRev"] == 1
    assert (await api.request("organizer-fsi", "PUT", url, json={"bodyMd": "x"})).status_code == 428
    assert (await api.request("organizer-fsi", "GET", url)).json()["bodyMd"] == "Entwurf"
    assert (await api.request("organizer-makers", "GET", url)).status_code == 404
    assert (await api.sql("SELECT count(*) FROM document_revision"))[0][0] == 1
    assert (await api.sql("SELECT body_md FROM document"))[0][0] == "# Eins\n\nzwei\n"
    huge = await api.request(
        "organizer-fsi", "PUT", url, json={"bodyMd": "x" * 300_000}, headers={"If-Match": '"1"'}
    )
    assert huge.status_code == 413
    assert (await api.request("organizer-fsi", "DELETE", url)).status_code == 204
    assert (await api.request("organizer-fsi", "GET", url)).status_code == 204


def corpus() -> list[str]:
    files = sorted(CORPUS_DIR.glob("*.md")) if CORPUS_DIR.is_dir() else []
    return [f.read_bytes().decode("utf-8") for f in files] or INLINE_CORPUS


async def test_document_body_stored_verbatim(api: Api) -> None:
    eid = await planning_event(api)
    doc = (await create_doc(api, eid, bodyMd="")).json()
    url = f"/api/documents/{doc['id']}"
    rev = 1
    for text in corpus():
        saved = await api.request(
            "organizer-fsi",
            "PUT",
            url,
            json={"bodyMd": text},
            headers={"If-Match": f'"{rev}"'},
        )
        assert saved.status_code == 200, saved.text
        rev = int(saved.headers["etag"].strip('"'))
        assert saved.json()["bodyMd"] == text
        got = await api.request("organizer-fsi", "GET", url)
        assert got.json()["bodyMd"].encode() == text.encode()
        stored = (await api.sql("SELECT body_md FROM document"))[0][0]
        assert stored.encode() == text.encode()


async def test_images_in_texts_are_recorded_and_never_removed(api: Api) -> None:
    eid = await planning_event(api)
    image = await api.request(
        "organizer-fsi",
        "POST",
        "/api/media/images",
        files={"file": ("a.png", png_bytes(), "image/png")},
    )
    assert image.status_code == 201, image.text
    iid, path = image.json()["id"], image.json()["url"]
    assert path == f"/api/media/images/{iid}"
    fetched = await api.request("viewer-fsi", "GET", path)
    assert fetched.status_code == 200 and fetched.headers["x-content-type-options"] == "nosniff"
    doc = (await create_doc(api, eid, bodyMd=f"![Bild]({path})\n")).json()
    refs = await api.sql("SELECT owner_type, owner_id::text FROM media_ref")
    assert [tuple(r) for r in refs] == [("document", doc["id"])]
    await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/documents/{doc['id']}",
        json={"bodyMd": "kein Bild mehr"},
        headers={"If-Match": '"1"'},
    )
    assert (await api.sql("SELECT count(*) FROM media_ref"))[0][0] == 1
    patched = await api.patch("organizer-fsi", eid, descriptionMd=f"x ![y]({path}) z")
    assert patched.status_code == 200, patched.text
    owners = {r[0] for r in await api.sql("SELECT owner_type FROM media_ref")}
    assert owners == {"document", "event"}


async def test_the_image_upload_needs_a_writing_role(api: Api) -> None:
    files = {"file": ("a.png", png_bytes(), "image/png")}
    assert (
        await api.request("viewer-fsi", "POST", "/api/media/images", files=files)
    ).status_code == 403
    assert (await api.request(None, "POST", "/api/media/images", files=files)).status_code == 401
    bad = await api.request(
        "organizer-fsi",
        "POST",
        "/api/media/images",
        files={"file": ("a.svg", b"<svg/>", "image/svg+xml")},
    )
    assert bad.status_code == 415
