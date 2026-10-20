"""Attachments over HTTP: kinds, rejects, names, quarantine, EICAR flow, EXIF, preview."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from tests._support import samples
from tests._support.factories import png_bytes
from tests.integration.dossier.helpers import clean_poster, planning_event, upload
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def test_every_kind_uploads_lists_and_groups(api: Api) -> None:
    eid = await planning_event(api)
    cases = [
        ("other", "foto.png", png_bytes(), "org"),
        ("quote", "angebot.pdf", samples.pdf_bytes(), "org"),
        ("contract", "vertrag.docx", samples.ooxml_bytes(".docx"), "org"),
        ("business_plan", "plan.xlsx", samples.ooxml_bytes(".xlsx"), "org"),
        ("howto_file", "ablauf.md", "# Ablauf €".encode(), "shared"),
        ("social_post", "post.png", png_bytes(), "org"),
    ]
    for kind, name, data, visibility in cases:
        form = {"meta": '{"channel": "instagram"}'} if kind == "social_post" else {}
        response = await upload(api, "organizer-fsi", eid, kind, name, data, **form)
        assert response.status_code == 201, (kind, response.text)
        out = response.json()
        assert out["scanStatus"] == "pending" and out["visibility"] == visibility
        assert out["kind"] == kind and out["hasPreview"] is False
    listed = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/attachments")).json()
    assert sorted(a["kind"] for a in listed) == sorted(c[0] for c in cases)
    only = await api.request("organizer-fsi", "GET", f"/api/events/{eid}/attachments?kind=quote")
    assert [a["displayName"] for a in only.json()] == ["angebot.pdf"]


async def test_hostile_uploads_are_refused_with_the_right_status(api: Api) -> None:
    eid = await planning_event(api)

    async def go(kind: str, name: str, data: bytes) -> tuple[int, str]:
        response = await upload(api, "organizer-fsi", eid, kind, name, data)
        return response.status_code, response.json().get("code", "")

    assert await go("other", "x.svg", samples.svg_bytes()) == (415, "unsupported_media_type")
    assert await go("other", "x.docm", samples.ooxml_bytes(".docx")) == (
        415,
        "unsupported_media_type",
    )
    assert (await go("other", "m.docx", samples.ooxml_bytes(".docx", macro=True)))[0] == 415
    assert await go("other", "foto.png", samples.exe_bytes()) == (415, "unsupported_media_type")
    assert await go("other", "a.docx", samples.zip_bomb_docx()) == (415, "archive_bomb")
    assert await go("quote", "a.pdf", samples.pdf_bytes(active=True)) == (415, "active_content")
    assert (await go("poster", "a.pdf", samples.pdf_bytes()))[0] == 415
    bomb = await upload(api, "organizer-fsi", eid, "other", "bombe.png", samples.bomb_png())
    assert bomb.status_code == 422 and bomb.json()["code"] == "image_rejected"
    assert bomb.json()["reason"] == "too_many_pixels"
    big = png_bytes() + b"\x00" * (10 * 1024 * 1024 + 1)
    too_big = await upload(api, "organizer-fsi", eid, "other", "gross.png", big)
    assert too_big.status_code == 413 and too_big.json()["limitBytes"] == 10 * 1024 * 1024
    assert (await api.sql("SELECT count(*) FROM attachment"))[0][0] == 0


async def test_a_poster_below_1200_px_is_too_small(api: Api) -> None:
    eid = await planning_event(api)
    small = await api.upload_poster("organizer-fsi", eid, data=png_bytes(400, 300))
    assert small.status_code == 422 and small.json()["code"] == "image_too_small"


async def test_a_euro_emoji_name_downloads_without_a_500(api: Api) -> None:
    eid = await planning_event(api)
    name = "Plakat 5 € 🎬.pdf"
    out = (await upload(api, "organizer-fsi", eid, "other", name, samples.pdf_bytes())).json()
    assert out["displayName"] == name
    assert await api.process_poster(out["id"]) == "clean"
    download = await api.request("organizer-fsi", "GET", f"/api/attachments/{out['id']}/download")
    assert download.status_code == 200 and download.content == samples.pdf_bytes()
    disposition = download.headers["content-disposition"]
    assert disposition.startswith("attachment;") and "filename*=UTF-8''" in disposition
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["cache-control"] == "private, no-store"


async def test_quarantine_pending_error_and_infected(api: Api) -> None:
    eid = await planning_event(api)
    out = (await upload(api, "organizer-fsi", eid, "quote", "a.pdf", samples.pdf_bytes())).json()
    url = f"/api/attachments/{out['id']}"
    pending = await api.request("organizer-fsi", "GET", f"{url}/download")
    assert pending.status_code == 409 and pending.json()["code"] == "quarantined"
    await api.sql("UPDATE attachment SET scan_status = 'error' WHERE id = :i", i=out["id"])
    assert (await api.request("organizer-fsi", "GET", f"{url}/download")).status_code == 409
    forbidden = await api.request("organizer-fsi", "POST", f"{url}/rescan")
    assert forbidden.status_code == 403
    assert (await api.request("editor", "POST", f"{url}/rescan")).status_code == 202
    assert api.queue.enqueued[-1].hex == out["id"].replace("-", "")
    assert (await api.sql("SELECT scan_status FROM attachment"))[0][0] == "pending"
    assert (await api.request("editor", "POST", f"{url}/rescan")).status_code == 409
    assert await api.process_poster(out["id"], signature="Eicar-Test-Signature") == "infected"
    gone = await api.request("organizer-fsi", "GET", f"{url}/download")
    assert gone.status_code == 410 and gone.json()["code"] == "attachment_infected"
    row = (await api.sql("SELECT storage_key, scan_result FROM attachment"))[0]
    assert row[0] is None and row[1] == "Eicar-Test-Signature"
    assert not [k for k in api.private.blobs if k.startswith(f"events/{eid}/quote/")]


async def test_an_infected_replacement_poster_blocks_approval(api: Api) -> None:
    event = await api.approved_ready_event()
    eid = event["id"]
    out = (await api.upload_poster("editor", eid, data=png_bytes())).json()
    assert await api.process_poster(out["id"], signature="Eicar-Test-Signature") == "infected"
    guards = (await api.request("editor", "GET", f"/api/events/{eid}/guards/T04")).json()
    assert "image_required" in [r["code"] for r in guards["reasons"]]
    assert (await api.fire("editor", eid, "T04")).status_code == 422


async def test_exif_gps_is_gone_from_download_preview_and_derivatives(api: Api) -> None:
    eid = await planning_event(api)
    out = (
        await upload(
            api,
            "organizer-fsi",
            eid,
            "other",
            "gps.jpg",
            samples.jpeg_with_gps(),
            visibility="shared",
        )
    ).json()
    assert await api.process_poster(out["id"]) == "clean"
    stored = await api.request("organizer-fsi", "GET", f"/api/attachments/{out['id']}/download")
    preview = await api.request("organizer-fsi", "GET", f"/api/attachments/{out['id']}/preview")
    assert preview.status_code == 200 and preview.headers["content-type"] == "image/webp"
    assert max(Image.open(io.BytesIO(preview.content)).size) == 400
    for blob in (stored.content, preview.content):
        assert len(Image.open(io.BytesIO(blob)).getexif()) == 0
    poster = await api.upload_poster(
        "organizer-fsi", eid, data=samples.jpeg_with_gps(), name="poster.jpg"
    )
    assert poster.status_code == 201, poster.text
    assert await api.process_poster(poster.json()["id"]) == "clean"
    assert api.public.blobs
    for key, blob in list(api.private.blobs.items()) + list(api.public.blobs.items()):
        assert b"TestCam" not in blob, key
        assert len(Image.open(io.BytesIO(blob)).getexif()) == 0, key


async def test_documents_have_no_preview(api: Api) -> None:
    eid = await planning_event(api)
    out = (await upload(api, "organizer-fsi", eid, "quote", "a.pdf", samples.pdf_bytes())).json()
    assert await api.process_poster(out["id"]) == "clean"
    preview = await api.request("organizer-fsi", "GET", f"/api/attachments/{out['id']}/preview")
    assert preview.status_code == 404


async def test_replace_hides_the_old_file_only_after_a_clean_scan(api: Api) -> None:
    eid = await planning_event(api)
    first = (
        await upload(api, "organizer-fsi", eid, "howto_file", "v1.md", b"eins", visibility="team")
    ).json()
    response = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/attachments/{first['id']}/replace",
        files={"file": ("v2.md", b"zwei", "text/markdown")},
    )
    assert response.status_code == 201, response.text
    second = response.json()
    assert second["supersedesId"] == first["id"] and second["visibility"] == "team"
    assert second["kind"] == "howto_file"
    url = f"/api/events/{eid}/attachments"
    plain = (await api.request("organizer-fsi", "GET", url)).json()
    assert {a["id"] for a in plain} == {first["id"], second["id"]}
    assert await api.process_poster(second["id"]) == "clean"
    plain = (await api.request("organizer-fsi", "GET", url)).json()
    assert [a["id"] for a in plain] == [second["id"]]
    all_rows = (await api.request("organizer-fsi", "GET", f"{url}?includeRetired=true")).json()
    old = next(a for a in all_rows if a["id"] == first["id"])
    assert old["retiredAt"] is not None and old["replacedBy"] == second["id"]


async def test_an_infected_replacement_keeps_the_old_file(api: Api) -> None:
    eid = await planning_event(api)
    first = (await upload(api, "organizer-fsi", eid, "quote", "a.pdf", samples.pdf_bytes())).json()
    second = (
        await api.request(
            "organizer-fsi",
            "POST",
            f"/api/attachments/{first['id']}/replace",
            files={"file": ("b.pdf", samples.pdf_bytes(), "application/pdf")},
        )
    ).json()
    assert await api.process_poster(second["id"], signature="Eicar-Test") == "infected"
    rows = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/attachments")).json()
    old = next(a for a in rows if a["id"] == first["id"])
    assert old["retiredAt"] is None


async def test_patch_validates_consent_visibility_and_social_posts(api: Api) -> None:
    eid = await planning_event(api)
    quote = (await upload(api, "organizer-fsi", eid, "quote", "a.pdf", samples.pdf_bytes())).json()
    shared = await upload(
        api, "organizer-fsi", eid, "quote", "b.pdf", samples.pdf_bytes(), visibility="shared"
    )
    assert shared.status_code == 422 and shared.json()["code"] == "visibility_not_allowed"
    patched = await api.request(
        "organizer-fsi", "PATCH", f"/api/attachments/{quote['id']}", json={"visibility": "shared"}
    )
    assert patched.status_code == 422 and patched.json()["code"] == "visibility_not_allowed"
    team = await api.request(
        "organizer-fsi", "PATCH", f"/api/attachments/{quote['id']}", json={"visibility": "team"}
    )
    assert team.status_code == 200 and team.json()["visibility"] == "team"
    image = (await upload(api, "organizer-fsi", eid, "other", "f.png", png_bytes())).json()
    consent = await api.request(
        "organizer-fsi", "PATCH", f"/api/attachments/{image['id']}", json={"personsDepicted": True}
    )
    assert consent.status_code == 422 and consent.json()["code"] == "consent_missing"
    post = (
        await upload(
            api,
            "organizer-fsi",
            eid,
            "social_post",
            "p.png",
            png_bytes(),
            meta='{"channel": "instagram"}',
        )
    ).json()
    planned = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/attachments/{post['id']}",
        json={"meta": {"channel": "instagram", "status": "planned"}},
    )
    assert planned.status_code == 422 and planned.json()["code"] == "rights_incomplete"
    ok = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/attachments/{post['id']}",
        json={
            "altText": "Alt",
            "credit": "Foto: Ada",
            "rightsBasis": "own_work",
            "meta": {"channel": "instagram", "status": "planned"},
        },
    )
    assert ok.status_code == 200, ok.text


async def test_retire_hides_a_file_but_not_the_published_poster(api: Api) -> None:
    eid = await planning_event(api)
    out = (await upload(api, "organizer-fsi", eid, "other", "a.png", png_bytes())).json()
    assert (
        await api.request("organizer-fsi", "POST", f"/api/attachments/{out['id']}/retire")
    ).status_code == 204
    assert (
        await api.request("organizer-fsi", "GET", f"/api/events/{eid}/attachments")
    ).json() == []
    live = await api.approved_ready_event()
    approved = await api.fire("editor", live["id"], "T04")
    assert approved.status_code == 200
    poster = live["poster"]["id"]
    blocked = await api.request("organizer-fsi", "POST", f"/api/attachments/{poster}/retire")
    assert blocked.status_code == 409 and blocked.json()["code"] == "poster_in_use"


async def test_closed_dossiers_take_no_attachments(api: Api) -> None:
    eid = await planning_event(api)
    await api.sql("UPDATE event SET state = 'archived' WHERE id = :i", i=eid)
    closed = await upload(api, "organizer-fsi", eid, "other", "a.png", png_bytes())
    assert closed.status_code == 409 and closed.json()["code"] == "dossier_closed"


async def test_the_database_nets_back_the_api(api: Api) -> None:
    eid = await planning_event(api)
    out = (await upload(api, "organizer-fsi", eid, "other", "a.png", png_bytes())).json()
    for statement in (
        "UPDATE attachment SET kind = 'quote', visibility = 'shared' WHERE id = :i",
        "UPDATE attachment SET kind = 'businessplan' WHERE id = :i",
        "UPDATE attachment SET size_bytes = 10485761 WHERE id = :i",
        "UPDATE attachment SET mime = 'application/pdf', size_bytes = 26214401 WHERE id = :i",
    ):
        with pytest.raises(Exception, match="ck_attachment"):
            await api.sql(statement, i=out["id"])
    await api.sql(
        "UPDATE attachment SET mime = 'application/pdf', size_bytes = 26214400 WHERE id = :i",
        i=out["id"],
    )


async def test_the_poster_route_alias_still_works_and_lists(api: Api) -> None:
    eid = await planning_event(api)
    poster = await clean_poster(api, eid)
    listed = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/attachments")).json()
    assert [a["id"] for a in listed] == [poster["id"]] and listed[0]["hasPreview"] is True
