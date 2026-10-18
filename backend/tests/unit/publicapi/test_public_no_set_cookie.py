"""Public responses never set a cookie and never resolve a session.

`CsrfMiddleware` issues the XSRF cookie on every other response that lacks one; it skips
the path prefix `/api/public/`, which the full-app test pins.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.publicapi.db import get_public_session
from app.modules.publicapi.router import router
from app.shared.errors import register_exception_handlers
from tests._support.factories import make_settings


class Empty:
    def all(self) -> list[object]:
        return []

    def scalars(self) -> list[object]:
        return []


class Session:
    async def execute(self, _statement: object) -> Empty:
        return Empty()


async def _override():  # noqa: ANN202
    yield Session()


PATHS = ("/api/public/feed/events", "/api/public/media/3fa9c1d2e4b5a678-card_1200.webp")


def test_the_public_router_itself_sets_no_cookie() -> None:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_public_session] = _override
    client = TestClient(app)
    for path in PATHS:
        assert "set-cookie" not in client.get(path, cookies={"ev_session": "x"}).headers, path


def test_public_feed_and_media_set_no_cookie_in_the_full_app() -> None:
    app = create_app(make_settings())
    app.dependency_overrides[get_public_session] = _override
    client = TestClient(app)
    for path in PATHS:
        assert "set-cookie" not in client.get(path, cookies={"ev_session": "x"}).headers, path
