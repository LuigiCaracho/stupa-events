"""User mail templates: catalog validation and strict rendering (contract M4, 5.6)."""

from __future__ import annotations

import pytest

from app.modules.notifications.placeholders import ALLOWED, find_problems, render_template
from app.shared.errors import ValidationProblem

_CTX = {
    "event": {"title": "Fest", "starts_local": "04.07.2026, 18:00 Uhr"},
    "venue": {"name": ""},
    "org": {"name": "FSI"},
}


def _codes(source: str) -> list[str]:
    return [p["code"] for p in find_problems(source)]


def test_template_validation() -> None:
    source = "{{ event.title }} {{ event.starts_local }} {{ venue.name }} {{ org.name }}"
    assert find_problems(source) == []
    unknown = find_problems("{{ event.raum }}")
    assert unknown[0]["code"] == "unknown_placeholder"
    assert unknown[0]["field"] == "event.raum"
    assert unknown[0]["allowed"] == list(ALLOWED)
    assert _codes("{% if event.title %}x{% endif %}") == ["statement_not_allowed"]
    assert _codes("{{ event.title|upper }}") == ["statement_not_allowed"]
    assert _codes("{{ event.title.upper() }}") == ["statement_not_allowed"]
    assert _codes("{{ event['title'] }}") == ["statement_not_allowed"]
    assert _codes("{{ 'x' }}") == ["statement_not_allowed"]
    assert _codes("{{ event }}") == ["unknown_placeholder"]
    assert _codes("{{ event.title ") == ["syntax_error"]
    assert find_problems("{# note #}Hallo") == []


def test_subject_with_newline_is_rejected() -> None:
    with pytest.raises(ValidationProblem) as err:
        render_template("a\nb", "x", _CTX)
    assert err.value.code == "subject_newline"


def test_unknown_placeholder_is_422_with_reasons() -> None:
    with pytest.raises(ValidationProblem) as err:
        render_template("Hallo", "{{ event.raum }}", _CTX)
    assert err.value.status == 422
    assert err.value.code == "template_invalid"
    assert (err.value.extensions or {})["reasons"][0]["code"] == "unknown_placeholder"


def test_template_render_strict() -> None:
    subject, body = render_template(
        "{{ event.title }}", "Am {{ event.starts_local }} bei {{ org.name }}{{ venue.name }}", _CTX
    )
    assert subject == "Fest"
    assert body == "Am 04.07.2026, 18:00 Uhr bei FSI"


def test_missing_context_key_is_422_not_500() -> None:
    with pytest.raises(ValidationProblem) as err:
        render_template("x", "{{ org.name }}", {"event": {}})
    assert (err.value.extensions or {})["reasons"][0]["code"] == "render_error"


def test_subject_length_limit() -> None:
    with pytest.raises(ValidationProblem) as err:
        render_template("a" * 201, "x", _CTX)
    assert (err.value.extensions or {})["reasons"][0]["code"] == "subject_too_long"
