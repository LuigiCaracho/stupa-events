"""Schemathesis against the public API (feed, media, calendars) and the feed JSON schema.

Generated cases (positive and negative, 200 examples per mode and operation) are drawn from
`/openapi.json` of the real app and sent through the integration client onto the real
database with the role `events_public`. Checks: no server error, documented status codes,
content types and schemas, plus two of our own: the feed answers the JSON schema file, and no
public answer sets a cookie or opens CORS.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import jsonschema_rs
import pytest
import schemathesis
from hypothesis import HealthCheck, given, settings
from hypothesis.errors import Unsatisfiable
from schemathesis.checks import not_a_server_error
from schemathesis.generation import GenerationMode
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    response_headers_conformance,
    response_schema_conformance,
    status_code_conformance,
)

from app.shared.errors import is_cookie_free_path
from tests.integration.archive.fixture import archived_movienight
from tests.integration.events.harness import Api
from tests.integration.publicapi import site_data
from tests.integration.subscriptions.subs_harness import (
    ADDRESS_KEY,
    HASH_KEY,
    SubsApi,
    subs,
    subs_url,
)

pytestmark = pytest.mark.integration
__fixtures__ = (subs, subs_url)
SCHEMA_FILE = Path(__file__).resolve().parents[2] / "schema" / "feed-v2.json"
FEED_SCHEMA = jsonschema_rs.validator_for(json.loads(SCHEMA_FILE.read_text()))
CHECKS = [
    not_a_server_error,
    status_code_conformance,
    content_type_conformance,
    response_schema_conformance,
    response_headers_conformance,
]
EXAMPLES = 200
CONTRACT = {
    name: jsonschema_rs.validator_for(schema)
    for name, schema in json.loads((SCHEMA_FILE.parent / "public-site-v1.json").read_text()).items()
}
CONTRACT.update(
    {
        f"map-{name}": jsonschema_rs.validator_for(schema)
        for name, schema in json.loads(
            (SCHEMA_FILE.parent / "public-map-v1.json").read_text()
        ).items()
    }
)
CONTRACT_OF = {
    "/api/public/map/events": "map-events",
    "/api/public/campus/buildings": "map-campus",
    "/api/public/campus/events": "search",
    "/api/public/events": "search",
    "/api/public/events/{slug}": "detail",
    "/api/public/today": "today",
    "/api/public/categories": "categories",
    "/api/public/calendar": "calendar",
    "/api/public/archive": "archive",
}


def draw(operation: Any, mode: GenerationMode) -> list[Any]:
    """Draw the cases of one operation (hypothesis is synchronous, so this runs in a thread)."""
    cases: list[Any] = []

    @settings(
        max_examples=EXAMPLES,
        deadline=None,
        database=None,
        suppress_health_check=list(HealthCheck),
    )
    @given(operation.as_strategy(generation_mode=mode))
    def collect(case: Any) -> None:
        cases.append(case)

    collect()
    return cases


def public_operations(api: Api) -> list[Any]:
    schema = schemathesis.openapi.from_dict(api.app.openapi())
    found = [result.ok() for result in schema.get_all_operations()]
    return [
        op
        for op in found
        if is_cookie_free_path(op.path.replace("{slug}", "x").replace("{token}", "x"))
    ]


async def test_schemathesis(subs: SubsApi) -> None:
    api = subs.api
    site_data.configure(
        api,
        pgcrypto_email_key=ADDRESS_KEY,
        email_hash_key=HASH_KEY,
        min_response_seconds=0,
    )
    await archived_movienight(api)
    await api.to_state("published", title="Zweiter Termin")
    operations = public_operations(api)
    assert {op.path for op in operations} == {
        "/api/public/feed/events",
        "/api/public/media/{name}",
        "/api/public/events",
        "/api/public/events/{slug}",
        "/api/public/today",
        "/api/public/categories",
        "/api/public/calendar",
        "/api/public/archive",
        "/api/public/map/events",
        "/api/public/campus/buildings",
        "/api/public/campus/events",
        "/ics/all.ics",
        "/ics/k/{slug}.ics",
        "/ics/e/{slug}.ics",
        "/",
        "/suche",
        "/kalender",
        "/rueckblick",
        "/e/{slug}",
        "/k/{slug}",
        "/sitemap.xml",
        "/robots.txt",
        "/start",
        "/abos",
        "/bestaetigen/{token}",
        "/abo/{token}",
        "/bestaetigen",
        "/abo",
        "/ics/p/{token}.ics",
        "/api/public/altcha/challenge",
        "/api/public/getstarted/questions",
        "/api/public/subscriptions",
        "/api/public/subscriptions/confirm",
        "/api/public/subscriptions/confirm/preview",
        "/api/public/subscriptions/manage-link",
        "/api/public/subscriptions/me",
        "/api/public/subscriptions/me/ics-token",
    }
    sent = 0
    for operation in operations:
        for mode in (GenerationMode.POSITIVE, GenerationMode.NEGATIVE):
            try:
                cases = await asyncio.to_thread(draw, operation, mode)
            except Unsatisfiable:
                assert mode is GenerationMode.NEGATIVE, operation.path
                continue
            for case in cases:
                kwargs = case.as_transport_kwargs(base_url="http://test")
                response = await api.client.request(**kwargs)
                case.validate_response(response, checks=CHECKS)
                assert "set-cookie" not in response.headers, case.path
                assert "access-control-allow-origin" not in response.headers, case.path
                if (
                    operation.path == "/api/public/feed/events"
                    and response.status_code == 200
                    and response.request.method == "GET"
                ):
                    FEED_SCHEMA.validate(response.json())
                if response.status_code == 200 and response.request.method == "GET":
                    contract = CONTRACT_OF.get(operation.path)
                    if contract:
                        CONTRACT[contract].validate(response.json())
                sent += 1
    assert sent >= 4 * EXAMPLES


def properties(spec: dict) -> tuple[set[str], set[str]]:
    return set(spec["properties"]), set(spec.get("required", []))


async def test_openapi_matches_feed_v2(api: Api) -> None:
    openapi = api.app.openapi()["components"]["schemas"]
    ours = json.loads(SCHEMA_FILE.read_text())
    resolve = lambda name: openapi[name]  # noqa: E731
    assert properties(resolve("PublicEventOut")) == properties(ours["$defs"]["event"])
    envelope, expected = properties(resolve("FeedOut")), properties(ours)
    assert envelope[0] == expected[0] and expected[1] - envelope[1] == {"schema"}
    nested = {
        "PublicOrganization": ours["$defs"]["event"]["properties"]["organization"],
        "PublicVenue": ours["$defs"]["event"]["properties"]["venue"]["oneOf"][1],
        "PublicFormat": ours["$defs"]["event"]["properties"]["format"]["oneOf"][1],
        "PublicImage": ours["$defs"]["event"]["properties"]["image"]["oneOf"][1],
        "PublicStatusReason": ours["$defs"]["event"]["properties"]["statusReason"]["oneOf"][1],
        "PublicCategory": ours["$defs"]["event"]["properties"]["categories"]["items"],
    }
    for name, spec in nested.items():
        assert properties(resolve(name)) == properties(spec), name
