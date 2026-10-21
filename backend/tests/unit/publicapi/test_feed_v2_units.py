"""Feed v2 units: the cursor, `since`, the sanitizer, the Python selection and the allowlist."""

from __future__ import annotations

import ast
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.modules.publicapi import allowlist, cursor, selection
from app.modules.publicapi import schemas as public_schemas
from app.modules.publicapi.ics.model import IcsRow
from app.modules.publicapi.router import parse_since, pick_organization
from app.modules.publicapi.service import (
    PUBLIC_EVENT_V,
    FeedQuery,
    feed_json,
    items_etag,
    to_public_event,
)
from app.modules.publicapi.textsafe import text_html
from app.shared.errors import BadRequestError, ValidationProblem
from tests.unit.publicapi.test_public_unit import row

ROOT = Path(__file__).resolve().parents[3] / "app" / "modules" / "publicapi"
NOW = datetime(2026, 10, 20, 9, tzinfo=UTC)


def test_cursor_round_trips_and_rejects_foreign_input() -> None:
    ident = uuid4()
    token = cursor.encode(NOW, ident)
    assert cursor.decode(token) == cursor.Cursor(NOW, ident)
    for bad in ("", "###", "e30=", "bm90LWpzb24=", cursor.encode(NOW, ident)[:-3]):
        with pytest.raises(ValidationProblem) as caught:
            cursor.decode(bad)
        assert caught.value.code == "invalid_cursor"
    naive = json.dumps({"startsAt": "2026-10-20T09:00:00", "id": str(ident)}).encode()
    import base64

    with pytest.raises(ValidationProblem):
        cursor.decode(base64.urlsafe_b64encode(naive).decode())


@pytest.mark.parametrize(
    "value", ["2026-10-20T09:00:00+02:00", "2026-10-20T07:00:00Z", "2026-10-20T07:00:00-05:30"]
)
def test_since_accepts_an_offset(value: str) -> None:
    assert parse_since(value) == datetime.fromisoformat(value)
    assert parse_since(None) is None


@pytest.mark.parametrize(
    "value", ["2026-10-20T09:00:00", "2026-10-20T09:00:00 02:00", "gestern", "2026-13-40T00:00:00Z"]
)
def test_since_without_a_usable_offset_is_a_400_with_a_hint(value: str) -> None:
    with pytest.raises(BadRequestError) as caught:
        parse_since(value)
    assert caught.value.code == "invalid_since" and "%2B02:00" in (caught.value.detail or "")


def test_organization_and_its_old_alias() -> None:
    assert pick_organization("fsi", None) == "fsi" and pick_organization(None, "fsi") == "fsi"
    assert pick_organization("fsi", "fsi") == "fsi" and pick_organization(None, None) is None
    with pytest.raises(ValidationProblem):
        pick_organization("fsi", "makers")


@pytest.mark.parametrize(
    ("markdown", "html"),
    [
        (None, None),
        ("   ", None),
        ("**fett** und *schief*", "<p><strong>fett</strong> und <em>schief</em></p>"),
        ("- a\n- b\n  - c", "<ul>\n<li>a</li>\n<li>b\n<ul>\n<li>c</li>\n</ul>\n</li>\n</ul>"),
        ("# Titel\n\nText", "Titel\n<p>Text</p>"),
        ("<script>alert(1)</script>", "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>"),
    ],
)
def test_text_html_allowlist(markdown: str | None, html: str | None) -> None:
    assert text_html(markdown) == html


@pytest.mark.parametrize(
    "markdown",
    [
        "[x](javascript:alert(1))",
        "[x](data:text/html;base64,AAAA)",
        "![bild](/api/media/images/00000000-0000-4000-8000-000000000000)",
        '<img src=x onerror="alert(1)">',
        "[x](//evil.example/path)",
    ],
)
def test_text_html_drops_active_content(markdown: str) -> None:
    rendered = text_html(markdown) or ""
    tags = set(re.findall(r"<\s*/?\s*([a-zA-Z0-9]+)", rendered))
    assert tags <= {"p", "a", "strong", "em", "ul", "ol", "li", "br"}
    for href in re.findall(r'href="([^"]*)"', rendered):
        assert href.startswith(("http://", "https://", "mailto:"))


def test_links_keep_http_https_mailto_and_get_rel() -> None:
    html = text_html("[a](https://x.example) [b](mailto:a@x.example)") or ""
    assert 'href="https://x.example"' in html and "mailto:a@x.example" in html
    assert 'rel="noopener noreferrer nofollow"' in html


def items(count: int) -> list:
    base = datetime(2026, 11, 1, 18, tzinfo=UTC)
    return [
        to_public_event(
            row(
                id=UUID(int=i + 1),
                slug=f"2026-11-0{i + 1}-e",
                starts_at=base + timedelta(days=i),
                ends_at=base + timedelta(days=i, hours=2),
                updated_at=NOW + timedelta(hours=i),
                category_slug="kino" if i % 2 == 0 else "party",
                category_parent_slug="fachschaft" if i == 0 else None,
                category_parent_name="Fachschaft" if i == 0 else None,
                category_parent_kind="fachschaft" if i == 0 else None,
                organization_slug="fsi" if i < 3 else "makers",
            ),
            "http://x",
        )
        for i in range(count)
    ]


def test_selection_filters_and_pages() -> None:
    feed = items(5)
    page, nxt = selection.page(feed, FeedQuery(limit=2))
    assert [i.id.int for i in page] == [1, 2] and nxt is not None
    after, nxt2 = selection.page(feed, FeedQuery(limit=2, cursor=cursor.decode(nxt)))
    assert [i.id.int for i in after] == [3, 4] and nxt2 is not None
    last, none = selection.page(feed, FeedQuery(limit=2, cursor=cursor.decode(nxt2)))
    assert [i.id.int for i in last] == [5] and none is None
    first = datetime(2026, 11, 3, tzinfo=UTC)
    assert [i.id.int for i in selection.page(feed, FeedQuery(start=first))[0]] == [3, 4, 5]
    assert [i.id.int for i in selection.page(feed, FeedQuery(end=first))[0]] == [1, 2]
    since = NOW + timedelta(hours=3)
    assert [i.id.int for i in selection.page(feed, FeedQuery(since=since))[0]] == [4, 5]
    assert [i.id.int for i in selection.page(feed, FeedQuery(category="party"))[0]] == [2, 4]
    assert [i.id.int for i in selection.page(feed, FeedQuery(category="fachschaft"))[0]] == [1]
    assert [i.id.int for i in selection.page(feed, FeedQuery(organization="makers"))[0]] == [4, 5]


def test_the_etag_covers_the_next_cursor_but_not_the_generation_time() -> None:
    feed = items(2)
    assert items_etag(feed) != items_etag(feed, "abc")
    body = json.loads(feed_json(feed, NOW, "abc"))
    assert body["nextCursor"] == "abc" and body["generatedAt"] == "2026-10-20T09:00:00Z"
    assert items_etag(feed, "abc") == items_etag(feed, "abc")


def model_fields(name: str) -> set[str]:
    return set(getattr(public_schemas, name).model_fields)


def test_public_allowlist_names_exactly_the_fields_of_the_models() -> None:
    for name, fields in allowlist.PUBLIC_FIELDS.items():
        if name == "IcsRow":
            assert fields == set(IcsRow.__dataclass_fields__)
        else:
            assert fields == model_fields(name), name
    declared = {
        name
        for name, value in vars(public_schemas).items()
        if isinstance(value, type)
        and issubclass(value, public_schemas.CamelModel)
        and value is not public_schemas.CamelModel
    }
    assert declared == set(allowlist.PUBLIC_FIELDS) - {"IcsRow"}


def test_the_view_columns_in_code_equal_the_allowlist() -> None:
    assert tuple(PUBLIC_EVENT_V.c.keys()) == allowlist.PUBLIC_VIEW_COLUMNS


FORBIDDEN_NAMES = {
    "model_dump",
    "model_validate",
    "from_attributes",
    "get_session",
    "Event",
    "Attachment",
}


def test_no_file_below_publicapi_dumps_models_or_imports_tables() -> None:
    offenders = []
    for source in sorted(ROOT.rglob("*.py")):
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            dumps = isinstance(node, ast.Attribute) and node.attr in {
                "model_dump",
                "model_validate",
            }
            if dumps or (isinstance(node, ast.Attribute) and node.attr == "dict"):
                offenders.append((source.name, node.attr))
            if isinstance(node, ast.keyword) and node.arg == "from_attributes":
                offenders.append((source.name, "from_attributes"))
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.endswith(".models") or node.module == "app.db":
                    offenders.append((source.name, node.module))
                if any(
                    alias.name in {"get_session", "Event", "Attachment"} for alias in node.names
                ):
                    offenders.append((source.name, [a.name for a in node.names]))
    assert not offenders, offenders
    assert FORBIDDEN_NAMES
