"""`gc_media` marks, sweeps and unmarks in two phases; `gc_notifications` ages out read rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

import worker.gc as gc
from tests._support.memory_storage import MemoryStorage
from tests.integration.events.harness import Api, FakePool

pytestmark = pytest.mark.integration

NOW = datetime(2026, 7, 20, 3, 50, tzinfo=UTC)


async def _image(api: Api, storage: MemoryStorage, age_days: int) -> UUID:
    image_id = uuid4()
    key = f"media/images/{image_id}"
    storage.blobs[key] = b"x"
    await api.sql(
        "INSERT INTO markdown_image (id, storage_key, mime, size, width, height, created_at) "
        "VALUES (:i, :k, 'image/png', 1, 1, 1, :c)",
        i=image_id,
        k=key,
        c=NOW - timedelta(days=age_days),
    )
    return image_id


async def _ids(api: Api) -> set[UUID]:
    return {r[0] for r in await api.sql("SELECT id FROM markdown_image")}


def _ctx(api: Api, storage: Any, redis: Any = None) -> dict[str, Any]:
    return {"gc_sessionmaker": api.maker, "object_storage": storage, "redis": redis}


async def test_gc_media_worker(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = MemoryStorage()
    old = await _image(api, storage, 8)
    young = await _image(api, storage, 3)
    in_old_revision = await _image(api, storage, 30)
    await api.sql(
        "INSERT INTO media_ref (image_id, owner_type, owner_id) VALUES (:i, 'document', :o)",
        i=in_old_revision,
        o=uuid4(),
    )
    clock = {"now": NOW}
    monkeypatch.setattr(gc, "utcnow", lambda: clock["now"])

    first = await gc.gc_media(_ctx(api, storage))
    assert "marked=1" in first
    assert await _ids(api) == {old, young, in_old_revision}
    marked = await api.sql("SELECT id FROM markdown_image WHERE gc_marked_at IS NOT NULL")
    assert marked == [(old,)]

    clock["now"] = NOW + timedelta(days=1, minutes=1)
    second = await gc.gc_media(_ctx(api, storage))
    assert "swept=1" in second
    assert await _ids(api) == {young, in_old_revision}
    assert f"media/images/{old}" not in storage.blobs
    assert f"media/images/{in_old_revision}" in storage.blobs


async def test_referenced_again_loses_mark_and_storage_error_keeps_row(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = MemoryStorage()
    saved = await _image(api, storage, 20)
    stuck = await _image(api, storage, 20)
    monkeypatch.setattr(gc, "utcnow", lambda: NOW)
    await gc.gc_media(_ctx(api, storage))
    await api.sql(
        "INSERT INTO media_ref (image_id, owner_type, owner_id) VALUES (:i, 'event', :o)",
        i=saved,
        o=uuid4(),
    )

    async def broken(key: str) -> None:
        raise OSError("bucket down")

    monkeypatch.setattr(gc, "utcnow", lambda: NOW + timedelta(days=2))
    storage.remove = broken  # type: ignore[method-assign]
    await gc.gc_media(_ctx(api, storage))
    assert await _ids(api) == {saved, stuck}
    assert await api.sql("SELECT id FROM markdown_image WHERE gc_marked_at IS NULL") == [(saved,)]


async def test_gc_media_is_idempotent_per_day(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gc, "utcnow", lambda: NOW)
    pool = FakePool()
    storage = MemoryStorage()
    assert (await gc.gc_media(_ctx(api, storage, pool))).startswith("gc_media:")
    assert await gc.gc_media(_ctx(api, storage, pool)) == "skipped"
    assert "gc_media:20260720" in pool.keys


async def test_gc_notifications_keeps_unread_and_recent(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gc, "utcnow", lambda: NOW)
    event = await api.create_event()
    for read_days, name in ((100, "old-read"), (10, "new-read"), (None, "unread")):
        await api.sql(
            "INSERT INTO notification (recipient_sub, kind, event_id, link, dedupe_key, read_at) "
            "VALUES ('s', 'comment_added', :e, '/dossiers/x', :n, :r)",
            e=event["id"],
            n=name,
            r=None if read_days is None else NOW - timedelta(days=read_days),
        )
    assert "deleted=1" in await gc.gc_notifications(_ctx(api, None))
    left = {r[0] for r in await api.sql("SELECT dedupe_key FROM notification")}
    assert left == {"new-read", "unread"}
