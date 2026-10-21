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

from tests.integration.archive.fixture import archived_movienight
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration
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
    return [op for op in found if op.path.startswith(("/api/public/", "/ics/"))]


async def test_schemathesis(api: Api) -> None:
    await archived_movienight(api)
    await api.to_state("published", title="Zweiter Termin")
    operations = public_operations(api)
    assert {op.path for op in operations} == {
        "/api/public/feed/events",
        "/api/public/media/{name}",
        "/ics/all.ics",
        "/ics/k/{slug}.ics",
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
