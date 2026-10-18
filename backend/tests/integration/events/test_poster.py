"""Poster upload, scan, derivatives and replacement."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from tests._support.factories import png_bytes
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def planning_event(api: Api, user: str = "organizer-fsi") -> str:
    event = await api.create_event(user=user)
    await api.fire(user, event["id"], "T01")
    return event["id"]


async def test_upload_stores_a_reencoded_pending_poster(api: Api) -> None:
    eid = await planning_event(api)
    big = io.BytesIO()
    Image.new("RGB", (80, 60), "#cc3333").save(big, "JPEG", exif=Image.Exif())
    response = await api.upload_poster(
        "organizer-fsi", eid, data=big.getvalue(), name="Plakat Ü.JPG"
    )
    assert response.status_code == 201, response.text
    out = response.json()
    assert out["scanStatus"] == "pending" and out["derivatives"] is None and out["kind"] == "poster"
    assert out["mime"] == "image/jpeg" and out["displayName"] == "Plakat Ü.JPG"
    assert out["altText"] == "Ein Filmplakat" and out["rightsBasis"] == "own_work"
    assert len(out["sha256"]) == 64 and api.queue.enqueued
    event = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}")).json()
    assert event["poster"]["id"] == out["id"] and event["rev"] == 3
    assert any(key.startswith(f"events/{eid}/poster/") for key in api.private.blobs)


async def test_scan_then_derive_makes_the_poster_usable(api: Api) -> None:
    eid = await planning_event(api)
    out = (await api.upload_poster("organizer-fsi", eid)).json()
    assert await api.process_poster(out["id"]) == "clean"
    event = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}")).json()
    derivatives = event["poster"]["derivatives"]
    assert event["poster"]["scanStatus"] == "clean"
    assert derivatives["card1200"]["id"] == f"{out['sha256'][:16]}-card_1200"
    assert (derivatives["card1200"]["width"], derivatives["card1200"]["height"]) == (1200, 675)
    assert derivatives["og1200x630"]["height"] == 630 and derivatives["thumb400"]["width"] == 400
    assert f"derivatives/{out['sha256'][:16]}-og_1200x630.webp" in api.public.blobs
    guards = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/guards/T04")).json()
    assert [r["code"] for r in guards["reasons"]] == ["forbidden"]
    editor = (await api.request("editor", "GET", f"/api/events/{eid}/guards/T04")).json()
    assert [r["code"] for r in editor["reasons"]] == ["invalid_transition"]
    assert editor["allowed"] is False
    file = await api.request(
        "organizer-fsi", "GET", f"/api/events/{eid}/poster/file?variant=thumb400"
    )
    assert file.status_code == 200 and file.headers["content-type"] == "image/webp"
    assert file.headers["cache-control"] == "private, max-age=300"
    assert Image.open(io.BytesIO(file.content)).width == 400


async def test_file_is_404_until_derivatives_exist_and_for_unknown_variants(api: Api) -> None:
    eid = await planning_event(api)
    assert (
        await api.request("organizer-fsi", "GET", f"/api/events/{eid}/poster/file")
    ).status_code == 404
    await api.upload_poster("organizer-fsi", eid)
    assert (
        await api.request("organizer-fsi", "GET", f"/api/events/{eid}/poster/file")
    ).status_code == 404
    bad = await api.request(
        "organizer-fsi", "GET", f"/api/events/{eid}/poster/file?variant=og1200x630"
    )
    assert bad.status_code == 422


async def test_an_infected_poster_is_quarantined_and_does_not_count(api: Api) -> None:
    eid = await planning_event(api)
    out = (await api.upload_poster("organizer-fsi", eid)).json()
    assert await api.process_poster(out["id"], signature="Eicar-Test-Signature") == "infected"
    await api.fire("organizer-fsi", eid, "T02")
    refused = await api.fire("editor", eid, "T04")
    assert refused.status_code == 422 and refused.json()["code"] == "image_required"
    event = (await api.request("editor", "GET", f"/api/events/{eid}")).json()
    assert event["poster"]["scanStatus"] == "infected"


async def test_replacing_keeps_the_old_poster_and_links_it(api: Api) -> None:
    eid = await planning_event(api)
    first = (await api.upload_poster("organizer-fsi", eid)).json()
    second = (await api.upload_poster("organizer-fsi", eid, data=png_bytes(color="#112233"))).json()
    assert second["supersedesId"] == first["id"] and second["sha256"] != first["sha256"]
    async with api.maker() as session:
        from sqlalchemy import text

        rows = (
            await session.execute(text("SELECT id::text, retired_at IS NOT NULL FROM attachment"))
        ).all()
    assert dict(rows) == {first["id"]: True, second["id"]: False}
    assert len(api.private.blobs) == 2


@pytest.mark.parametrize(
    ("data", "name", "status"),
    [
        (b"not an image at all", "poster.png", 415),
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "poster.svg", 415),
        (png_bytes(), "poster.exe", 415),
        (b"GIF89a" + b"\x00" * 40, "poster.gif", 415),
        (b"x" * (10 * 1024 * 1024 + 1), "poster.png", 413),
    ],
)
async def test_bad_uploads(api: Api, data: bytes, name: str, status: int) -> None:
    eid = await planning_event(api)
    response = await api.upload_poster("organizer-fsi", eid, data=data, name=name)
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    assert not api.private.blobs


async def test_decompression_bomb_is_refused(api: Api) -> None:
    eid = await planning_event(api)
    bomb = io.BytesIO()
    Image.new("1", (30000, 30000)).save(bomb, "PNG")
    assert len(bomb.getvalue()) < 10 * 1024 * 1024
    assert (await api.upload_poster("organizer-fsi", eid, data=bomb.getvalue())).status_code == 415


@pytest.mark.parametrize(
    "fields",
    [
        {"altText": ""},
        {"credit": ""},
        {"rightsBasis": "mine"},
        {"altText": "x" * 251},
        {"credit": "x" * 201},
    ],
)
async def test_metadata_is_required_and_bounded(api: Api, fields: dict[str, str]) -> None:
    eid = await planning_event(api)
    response = await api.upload_poster("organizer-fsi", eid, **fields)
    assert response.status_code == 422 and response.json()["code"] == "validation_error"


async def test_missing_file_is_422(api: Api) -> None:
    eid = await planning_event(api)
    response = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/poster",
        data={"altText": "a", "credit": "c", "rightsBasis": "own_work"},
    )
    assert response.status_code == 422


async def test_upload_rights_by_state(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    assert (await api.upload_poster("organizer-fsi", eid)).status_code == 201
    await api.fire("organizer-fsi", eid, "T01")
    await api.fire("organizer-fsi", eid, "T02")
    assert (await api.upload_poster("organizer-fsi", eid)).status_code == 403
    assert (await api.upload_poster("approver-fsi", eid)).status_code == 403
    assert (await api.upload_poster("editor", eid)).status_code == 201


async def test_upload_is_locked_once_approved(api: Api) -> None:
    ready = await api.approved_ready_event()
    await api.fire("editor", ready["id"], "T04")
    locked = await api.upload_poster("editor", ready["id"])
    assert locked.status_code == 409 and locked.json()["code"] == "field_locked"


async def test_storage_off_is_503(api: Api) -> None:
    from app.main import create_app  # noqa: F401
    from app.modules.dossier.deps import attachment_storage

    eid = await planning_event(api)
    api.client._transport.app.dependency_overrides[attachment_storage] = lambda: None  # type: ignore[attr-defined]
    assert (await api.upload_poster("organizer-fsi", eid)).status_code == 503


async def test_scan_job_without_clean_status_does_not_derive(api: Api) -> None:
    from app.modules.dossier.derive import derive_poster

    eid = await planning_event(api)
    out = (await api.upload_poster("organizer-fsi", eid)).json()
    ctx = {
        "object_storage": api.private,
        "public_storage": api.public,
        "files_sessionmaker": api.maker,
    }
    assert await derive_poster(ctx, out["id"]) == "skipped"
    assert await derive_poster({**ctx, "public_storage": None, "settings": None}, out["id"]) in {
        "skipped"
    }
    assert await api.process_poster(out["id"]) == "clean"
    assert await derive_poster(ctx, out["id"]) == "derived"
    assert await derive_poster(ctx, "00000000-0000-0000-0000-000000000000") == "gone"
