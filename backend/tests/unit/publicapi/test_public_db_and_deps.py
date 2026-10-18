"""The public engine has no fallback; the dossier dependencies read the app state."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.dossier import deps
from app.modules.publicapi import db
from app.shared.errors import ServiceUnavailableError
from tests._support.factories import make_settings


@pytest.fixture(autouse=True)
def fresh_engine():  # noqa: ANN201
    db.get_public_engine.cache_clear()
    deps._public_storage.cache_clear()
    yield
    db.get_public_engine.cache_clear()
    deps._public_storage.cache_clear()


def test_without_a_public_url_there_is_no_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "get_settings", lambda: make_settings())
    with pytest.raises(ServiceUnavailableError):
        db.get_public_engine()


async def test_the_engine_uses_the_public_url_only(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql+asyncpg://events_public:pw@db/events"
    monkeypatch.setattr(db, "get_settings", lambda: make_settings(public_database_url=url))
    engine = db.get_public_engine()
    assert engine.url.username == "events_public" and db.get_public_engine() is engine
    sessions = db.get_public_session()
    session = await anext(sessions)
    assert session.bind is engine
    await sessions.aclose()
    await engine.dispose()


def test_dependencies_read_the_app_state(monkeypatch: pytest.MonkeyPatch) -> None:
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(object_storage="S", arq_pool=None))
    )
    assert deps.attachment_storage(request) == "S"  # type: ignore[arg-type]
    assert deps.scan_queue(request) is None  # type: ignore[arg-type]
    bare = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    assert deps.attachment_storage(bare) is None  # type: ignore[arg-type]
    pooled = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(arq_pool=object())))
    assert deps.scan_queue(pooled) is not None  # type: ignore[arg-type]


def test_public_storage_follows_the_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps, "get_settings", lambda: make_settings())
    assert deps.public_storage() is None
    deps._public_storage.cache_clear()
    monkeypatch.setattr(
        deps,
        "get_settings",
        lambda: make_settings(
            minio_endpoint="minio:9000", minio_access_key="a", minio_secret_key="b"
        ),
    )
    storage = deps.public_storage()
    assert storage is not None and storage.bucket == "events-public"  # type: ignore[attr-defined]
