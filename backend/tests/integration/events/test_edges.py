"""Races, storage failures and rare paths that the happy-path suites do not reach."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.modules.dossier import posters
from app.modules.dossier.deps import attachment_storage
from app.modules.dossier.derive import derive_poster
from app.modules.files.storage import StorageError
from app.modules.media.images import CleanImage
from app.modules.pipeline import exception as exception_module
from tests._support.memory_storage import MemoryStorage
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


class BrokenStorage(MemoryStorage):
    async def put(self, key: str, data: bytes, content_type: str) -> None:
        raise StorageError("down")

    async def get(self, key: str) -> bytes:
        raise StorageError("down")


async def planning(api: Api) -> str:
    event = await api.create_event()
    await api.fire("organizer-fsi", event["id"], "T01")
    return event["id"]


async def test_a_reader_without_attach_right_in_the_event_org_is_403(api: Api) -> None:
    eid = await planning(api)
    await api.add_user(
        "reader", {"makers-team": ("organizer", "makers"), "fsi-readers": ("viewer", "fsi")}
    )
    assert (await api.upload_poster("reader", eid)).status_code == 403
    patch = await api.request(
        "reader", "PATCH", f"/api/events/{eid}", json={"rev": 2, "summary": "x"}
    )
    assert patch.status_code == 403


async def test_storage_write_failure_is_503_and_nothing_is_kept(api: Api) -> None:
    eid = await planning(api)
    api.client._transport.app.dependency_overrides[attachment_storage] = lambda: BrokenStorage()  # type: ignore[attr-defined]
    assert (await api.upload_poster("organizer-fsi", eid)).status_code == 503
    async with api.maker() as session:
        assert (await session.execute(text("SELECT count(*) FROM attachment"))).scalar_one() == 0


async def test_an_oversize_reencode_is_413(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    eid = await planning(api)
    huge = CleanImage(data=b"x" * (11 * 1024 * 1024), mime="image/png", width=1, height=1)
    monkeypatch.setattr(posters, "_clean_bounded", lambda data: huge)
    assert (await api.upload_poster("organizer-fsi", eid)).status_code == 413


async def test_a_race_on_the_hero_link_is_409(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    eid = await planning(api)
    real = posters.load_visible

    async def stale(session, principal, event_id):  # noqa: ANN001, ANN202
        event = await real(session, principal, event_id)
        session.expunge(event)
        event.rev -= 1
        return event

    monkeypatch.setattr(posters, "load_visible", stale)
    assert (await api.upload_poster("organizer-fsi", eid)).status_code == 409


async def test_poster_file_failures(api: Api) -> None:
    eid = await planning(api)
    out = (await api.upload_poster("organizer-fsi", eid)).json()
    await api.process_poster(out["id"])
    path = f"/api/events/{eid}/poster/file"
    from app.modules.dossier.deps import public_storage

    overrides = api.client._transport.app.dependency_overrides  # type: ignore[attr-defined]
    overrides[public_storage] = lambda: None
    assert (await api.request("organizer-fsi", "GET", path)).status_code == 503
    overrides[public_storage] = lambda: BrokenStorage()
    assert (await api.request("organizer-fsi", "GET", path)).status_code == 503


async def test_upload_without_a_queue_still_succeeds(api: Api) -> None:
    from app.modules.dossier.deps import scan_queue

    eid = await planning(api)
    api.client._transport.app.dependency_overrides[scan_queue] = lambda: None  # type: ignore[attr-defined]
    assert (await api.upload_poster("organizer-fsi", eid)).status_code == 201


async def test_exception_on_a_live_event_is_locked_and_the_service_checks_the_right(
    api: Api,
) -> None:
    ready = await api.approved_ready_event()
    await api.fire("editor", ready["id"], "T04")
    await api.fire("editor", ready["id"], "T05")
    locked = await api.request(
        "editor",
        "POST",
        f"/api/events/{ready['id']}/image-exception",
        json={"reason": "Nachträglich ohne Bild"},
    )
    assert locked.status_code == 409 and locked.json()["code"] == "field_locked"


async def test_exception_service_refuses_a_principal_without_the_right(api: Api) -> None:
    from app.modules.auth.principal import Principal
    from app.shared.errors import ForbiddenError
    from tests._support.factories import make_principal

    eid = await planning(api)
    organizer: Principal = make_principal("events-fsi-organizer")
    async with api.maker() as session:
        from app.modules.orgs.scope import bind

        await bind(session, organizer)
        with pytest.raises(ForbiddenError):
            await exception_module.grant_image_exception(
                session, organizer, __import__("uuid").UUID(eid), "Ein langer Grund"
            )


async def race_after_load(
    api: Api, monkeypatch: pytest.MonkeyPatch, module: object, eid: str
) -> None:
    """Make another writer bump `rev` right after the dossier was loaded (a real race)."""
    real = module.load_visible  # type: ignore[attr-defined]

    async def racing(session, principal, event_id):  # noqa: ANN001, ANN202
        event = await real(session, principal, event_id)
        async with api.maker() as other:
            await other.execute(text("UPDATE event SET rev = rev + 1 WHERE id = :i"), {"i": eid})
            await other.commit()
        return event

    monkeypatch.setattr(module, "load_visible", racing)


async def test_exception_race_is_409(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.pipeline import action_base

    eid = await planning(api)
    await race_after_load(api, monkeypatch, action_base, eid)
    response = await api.request(
        "editor", "POST", f"/api/events/{eid}/image-exception", json={"reason": "Ein langer Grund"}
    )
    assert response.status_code == 409 and response.json()["code"] == "conflict"
    assert response.json()["currentRev"] == 3 and response.json()["current"]["rev"] == 3


async def test_patch_race_is_409(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.events import service as events_service

    eid = await planning(api)
    await race_after_load(api, monkeypatch, events_service, eid)
    response = await api.request(
        "organizer-fsi", "PATCH", f"/api/events/{eid}", json={"rev": 2, "summary": "x"}
    )
    assert response.status_code == 409 and response.json()["code"] == "conflict"


async def test_an_event_without_organization_is_for_editors_and_not_for_posters(api: Api) -> None:
    async with api.maker() as session:
        await session.execute(
            text(
                "INSERT INTO event (id, title, starts_at, ends_at, created_by, state) VALUES "
                "('00000000-0000-0000-0000-0000000000aa', 'Vorschlag', now() + interval '2 days', "
                "now() + interval '3 days', 'someone', 'idea')"
            )
        )
        await session.commit()
    url = "/api/events/00000000-0000-0000-0000-0000000000aa"
    assert (await api.request("organizer-fsi", "GET", url)).status_code == 404
    seen = await api.request("editor", "GET", url)
    assert seen.status_code == 200 and seen.json()["organization"] is None
    patched = await api.request("editor", "PATCH", url, json={"rev": 1, "summary": "x"})
    assert patched.status_code == 200
    assert (
        await api.request("organizer-fsi", "PATCH", url, json={"rev": 2, "summary": "x"})
    ).status_code == 404
    assert (
        await api.upload_poster("editor", "00000000-0000-0000-0000-0000000000aa")
    ).status_code == 403


async def test_derive_handles_garbage_and_storage_errors(api: Api) -> None:
    eid = await planning(api)
    out = (await api.upload_poster("organizer-fsi", eid)).json()
    await api.process_poster(out["id"])
    async with api.maker() as session:
        await session.execute(text("UPDATE attachment SET derivatives = NULL"))
        await session.commit()
        key = (await session.execute(text("SELECT storage_key FROM attachment"))).scalar_one()
    ctx = {
        "object_storage": api.private,
        "public_storage": api.public,
        "files_sessionmaker": api.maker,
    }
    original = api.private.blobs[key]
    api.private.blobs[key] = b"not an image"
    assert await derive_poster(ctx, out["id"]) == "rejected"
    api.private.blobs[key] = original
    with pytest.raises(StorageError):
        await derive_poster({**ctx, "public_storage": BrokenStorage()}, out["id"])
