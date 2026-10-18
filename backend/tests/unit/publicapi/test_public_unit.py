"""Public API units: view rows to wire shape, ETag, headers, media ids, lint."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import jsonschema_rs
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.dossier.deps import public_storage
from app.modules.files.storage import StorageError
from app.modules.publicapi import service
from app.modules.publicapi.db import get_public_session
from app.modules.publicapi.router import _matches
from tests._support.factories import make_settings
from tests._support.memory_storage import MemoryStorage

SCHEMA = jsonschema_rs.validator_for(
    json.loads((Path(__file__).resolve().parents[2] / "schema" / "feed-v2.json").read_text())
)
SHA = "3fa9c1d2e4b5a678" + "0" * 48


def row(**over: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "id": uuid4(),
        "slug": "2026-11-05-movienight",
        "title": "Movienight",
        "summary": "Kurz",
        "starts_at": datetime(2026, 11, 5, 19, 0, tzinfo=timezone(timedelta(hours=1))),
        "ends_at": datetime(2026, 11, 5, 21, 0, tzinfo=UTC),
        "all_day": False,
        "tzid": "Europe/Berlin",
        "public_status": "scheduled",
        "organization_id": uuid4(),
        "organization_slug": "fsi",
        "organization_name": "Fachschaft Informatik",
        "organization_short": "FSI",
        "venue_text": "Kinosaal",
        "category_slug": "kino",
        "category_name": "Kino",
        "category_kind": "format",
        "hero_sha": SHA,
        "hero_derivatives": {
            "card_1200": {"id": f"{SHA[:16]}-card_1200", "width": 1200, "height": 675}
        },
        "hero_alt": "Alt",
        "hero_credit": "Credit",
    }
    return SimpleNamespace(**{**base, **over})


def feed_of(rows: list[SimpleNamespace]) -> dict[str, Any]:
    items = [service.to_public_event(r, "http://x") for r in rows]  # type: ignore[arg-type]
    return json.loads(service.feed_json(items, datetime(2026, 10, 18, 12, tzinfo=UTC)))


def test_row_shapes_to_the_contract() -> None:
    feed = feed_of([row()])
    SCHEMA.validate(feed)
    item = feed["items"][0]
    assert feed["schema"] == 2 and feed["generatedAt"] == "2026-10-18T12:00:00Z"
    assert item["startsAt"] == "2026-11-05T18:00:00Z"
    assert item["image"]["url"] == f"http://x/api/public/media/{SHA[:16]}-card_1200.webp"
    assert item["url"] == "http://x/e/2026-11-05-movienight"
    assert item["categories"] == [{"slug": "kino", "name": "Kino", "kind": "format"}]


def test_exception_event_has_no_image_and_no_category_means_empty_list() -> None:
    plain = row(hero_sha=None, hero_derivatives=None, category_slug=None, venue_text=None)
    feed = feed_of([plain])
    SCHEMA.validate(feed)
    assert feed["items"][0]["image"] is None
    assert feed["items"][0]["categories"] == [] and feed["items"][0]["venueText"] is None


def test_feed_never_carries_internal_fields() -> None:
    dumped = json.dumps(feed_of([row()]))
    for forbidden in (
        "createdBy",
        "imageException",
        "note",
        "hero",
        "organizationSlug",
        "updatedAt",
    ):
        assert forbidden not in dumped


def test_etag_ignores_generation_time_and_follows_content() -> None:
    a = [service.to_public_event(row(), "http://x")]  # type: ignore[arg-type]
    same = [
        service.to_public_event(a_row, "http://x")
        for a_row in [row(id=a[0].id, organization_id=a[0].organization.id)]
    ]  # type: ignore[arg-type]
    other = [service.to_public_event(row(title="Anders"), "http://x")]  # type: ignore[arg-type]
    assert service.items_etag(a) == service.items_etag(same) != service.items_etag(other)
    assert service.items_etag(a).startswith('"') and service.items_etag(a).endswith('"')


@pytest.mark.parametrize(
    ("header", "etag", "want"),
    [
        (None, '"a"', False),
        ('"a"', '"a"', True),
        ('W/"a"', '"a"', True),
        ('"b", "a"', '"a"', True),
        ("*", '"a"', True),
        ('"b"', '"a"', False),
    ],
)
def test_if_none_match(header: str | None, etag: str, want: bool) -> None:
    assert _matches(header, etag) is want


class Result:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def all(self) -> list[Any]:
        return self.rows

    def scalars(self) -> Iterator[Any]:
        return iter(self.rows)


class Session:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows
        self.statements: list[str] = []

    async def execute(self, statement: Any) -> Result:
        self.statements.append(str(statement.compile(compile_kwargs={"literal_binds": True})))
        return Result(self.rows)


@pytest.fixture
def client_for():  # noqa: ANN201
    def build(rows: list[Any], storage: Any = None) -> tuple[TestClient, Session]:
        session = Session(rows)
        app = create_app(make_settings())

        async def override() -> Any:
            yield session

        app.dependency_overrides[get_public_session] = override
        app.dependency_overrides[public_storage] = lambda: storage
        return TestClient(app), session

    return build


def test_feed_route_headers_filters_and_304(client_for) -> None:  # noqa: ANN001
    client, session = client_for([row()])
    response = client.get(
        "/api/public/feed/events",
        params={
            "from": "2026-11-01T00:00:00Z",
            "to": "2026-12-01T00:00:00Z",
            "category": "kino",
            "org": "fsi",
        },
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300, stale-while-revalidate=60"
    assert response.headers["x-robots-tag"] == "noindex"
    assert "access-control-allow-origin" not in response.headers
    SCHEMA.validate(response.json())
    sql = session.statements[0]
    assert "category_slug = 'kino'" in sql and "organization_slug = 'fsi'" in sql
    assert "ORDER BY public_event_v.starts_at, public_event_v.id" in sql
    again = client.get(
        "/api/public/feed/events", headers={"If-None-Match": response.headers["etag"]}
    )
    assert again.status_code == 304 and again.content == b""
    assert again.headers["etag"] == response.headers["etag"]


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=501", "from=2026-11-01T00:00:00", "from=nonsense"]
)
def test_feed_route_rejects_bad_queries_as_problem_json(client_for, query: str) -> None:  # noqa: ANN001
    client, _ = client_for([])
    response = client.get(f"/api/public/feed/events?{query}")
    assert response.status_code == 422 and response.headers["content-type"].startswith(
        "application/problem+json"
    )


class BrokenStorage(MemoryStorage):
    async def get(self, key: str) -> bytes:
        raise StorageError("down")


CARD = {"card_1200": {"id": f"{SHA[:16]}-card_1200"}}


def test_media_route(client_for) -> None:  # noqa: ANN001
    storage = MemoryStorage()
    key = f"derivatives/{SHA[:16]}-card_1200.webp"
    storage.blobs[key] = b"RIFFwebp"
    derivatives = {"card_1200": {"id": f"{SHA[:16]}-card_1200"}}
    client, session = client_for([derivatives], storage)
    ok = client.get(f"/api/public/media/{SHA[:16]}-card_1200.webp")
    assert ok.status_code == 200 and ok.content == b"RIFFwebp"
    assert ok.headers["content-type"] == "image/webp"
    assert ok.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert f"left(public_event_v.hero_sha, 16) = '{SHA[:16]}'" in session.statements[0]
    for bad in ("nonsense.webp", f"{SHA[:16]}-huge.webp", f"{SHA[:16]}-card_1200", "../x.webp"):
        assert client.get(f"/api/public/media/{bad}").status_code == 404


def test_media_route_for_a_derivative_of_no_public_event_is_404(client_for) -> None:  # noqa: ANN001
    client, _ = client_for([], MemoryStorage())
    assert client.get(f"/api/public/media/{SHA[:16]}-card_1200.webp").status_code == 404
    other_variant, _ = client_for([{"thumb_400": {}}], MemoryStorage())
    assert other_variant.get(f"/api/public/media/{SHA[:16]}-card_1200.webp").status_code == 404
    other_id, _ = client_for([{"card_1200": {"id": "ffffffffffffffff-card_1200"}}], MemoryStorage())
    assert other_id.get(f"/api/public/media/{SHA[:16]}-card_1200.webp").status_code == 404


def test_media_route_storage_failures_are_503(client_for) -> None:  # noqa: ANN001
    path = f"/api/public/media/{SHA[:16]}-card_1200.webp"
    off, _ = client_for([CARD], None)
    broken, _ = client_for([CARD], BrokenStorage())
    assert off.get(path).status_code == 503 and broken.get(path).status_code == 503


def test_public_module_builds_responses_field_by_field() -> None:
    root = Path(__file__).resolve().parents[3] / "app" / "modules" / "publicapi"
    for source in root.glob("*.py"):
        body = source.read_text()
        code = "\n".join(line for line in body.splitlines() if "`model_dump`" not in line)
        assert "model_dump(" not in code and "from_attributes" not in code, source.name
        assert ".dict(" not in code and "model_validate(" not in code, source.name
