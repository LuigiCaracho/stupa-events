"""Item e of the M5 acceptance: Schemathesis against the public operations of the dev API.

The schema is the `/openapi.json` of the running API; the cases (positive and negative,
200 per mode and operation) go over HTTP to the dev stack. Checks as in
`tests/integration/publicapi/test_schemathesis.py`: no server error, documented status codes,
content types, schemas and headers, the feed against `tests/schema/feed-v2.json`, and no
cookie and no CORS header on any public answer.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import httpx
import jsonschema_rs
import schemathesis
from hypothesis.errors import Unsatisfiable
from schemathesis.generation import GenerationMode

from scripts.acceptance_common import API, step
from tests.integration.publicapi.test_schemathesis import CHECKS, draw

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "tests" / "schema" / "feed-v2.json"
PUBLIC = ("/api/public/", "/ics/")


def _operations() -> list[Any]:
    spec = httpx.get(f"{API}/openapi.json", timeout=30).json()
    schema = schemathesis.openapi.from_dict(spec)
    found = [cast(Any, result).ok() for result in schema.get_all_operations()]
    return [op for op in found if op.path.startswith(PUBLIC)]


async def run_schemathesis() -> tuple[int, list[str]]:
    """Send every drawn case; return the number sent and the failures."""
    feed_schema = jsonschema_rs.validator_for(json.loads(SCHEMA_FILE.read_text()))
    failures: list[str] = []
    sent = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for operation in _operations():
            for mode in (GenerationMode.POSITIVE, GenerationMode.NEGATIVE):
                try:
                    cases = await asyncio.to_thread(draw, operation, mode)
                except Unsatisfiable:
                    continue
                for case in cases:
                    response = await client.request(**case.as_transport_kwargs(base_url=API))
                    sent += 1
                    try:
                        case.validate_response(response, checks=CHECKS)
                        assert "set-cookie" not in response.headers, "cookie"
                        assert "access-control-allow-origin" not in response.headers, "cors"
                        if (
                            operation.path.endswith("/feed/events")
                            and response.status_code == 200
                            and case.method == "GET"
                        ):
                            feed_schema.validate(response.json())
                    except Exception as exc:  # noqa: BLE001 - collected and reported
                        failures.append(f"{case.method} {response.request.url}: {exc}"[:300])
            step(f"e: {operation.method.upper()} {operation.path}: {sent} cases so far")
    return sent, failures
