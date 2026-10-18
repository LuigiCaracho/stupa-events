"""Contract: the JSON on the wire is camelCase, in every schema of the OpenAPI document."""

from __future__ import annotations

import re

from app.main import create_app
from tests._support.factories import make_settings

_CAMEL = re.compile(r"^[a-z][A-Za-z0-9]*$")
_EXEMPT = {"traceId"}


def _schema_names() -> dict[str, list[str]]:
    schema = create_app(make_settings()).openapi()
    components = schema["components"]["schemas"]
    return {name: list(body.get("properties", {})) for name, body in components.items()}


def test_every_property_is_camel_case() -> None:
    offenders = {
        name: [p for p in props if p not in _EXEMPT and not _CAMEL.match(p)]
        for name, props in _schema_names().items()
        if name != "HTTPValidationError"
    }
    assert not {k: v for k, v in offenders.items() if v}


def test_problem_detail_and_me_are_documented() -> None:
    names = _schema_names()
    assert {"ProblemDetail", "MeOut", "LogoutOut"} <= set(names)
    assert {"displayName", "organizations"} <= set(names["MeOut"])
