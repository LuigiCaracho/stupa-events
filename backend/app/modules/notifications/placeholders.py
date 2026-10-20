"""Placeholder catalog and validation of user mail templates (dossier `mail_template`).

Only `{{ path }}` expressions with a catalog path are allowed. Statements, filters, calls,
index access, literals and unknown paths are findings; each finding is a `reason`. The
subject carries no CR or LF and is at most 200 characters. Rendering uses the Jinja
sandbox with `StrictUndefined` as the second safety net. The server never sends these mails.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jinja2 import StrictUndefined, TemplateError, TemplateSyntaxError, nodes
from jinja2.sandbox import SandboxedEnvironment

from app.modules.notifications.templating import TemplateRenderError
from app.shared.errors import ValidationProblem

SUBJECT_MAX = 200
_ENV = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)


@dataclass(frozen=True, slots=True)
class Placeholder:
    """One catalog entry."""

    path: str
    label: str
    example: str


CATALOG: tuple[Placeholder, ...] = (
    Placeholder("event.title", "Titel der Veranstaltung", "Sommerfest der Fachschaft"),
    Placeholder("event.starts_local", "Beginn in Ortszeit", "04.07.2026, 18:00 Uhr"),
    Placeholder("venue.name", "Name des Ortes", "Mensa Reutlingen"),
    Placeholder("org.name", "Name der Organisation", "Fachschaft Informatik"),
)
ALLOWED: tuple[str, ...] = tuple(p.path for p in CATALOG)


def _reason(code: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, **extra}


def _path(node: nodes.Node) -> str | None:
    if isinstance(node, nodes.Name):
        return node.name
    if isinstance(node, nodes.Getattr):
        head = _path(node.node)
        return None if head is None else f"{head}.{node.attr}"
    return None


def _check_output(node: nodes.Node) -> dict[str, Any] | None:
    if isinstance(node, nodes.TemplateData):
        return None
    path = _path(node)
    if path is None:
        return _reason("statement_not_allowed", line=node.lineno)
    if path not in ALLOWED:
        return _reason("unknown_placeholder", field=path, line=node.lineno, allowed=list(ALLOWED))
    return None


def find_problems(source: str) -> list[dict[str, Any]]:
    """Return one reason per finding in a template source (empty list: valid)."""
    try:
        tree = _ENV.parse(source)
    except TemplateSyntaxError as exc:
        return [_reason("syntax_error", line=exc.lineno, message=exc.message)]
    problems: list[dict[str, Any]] = []
    for stmt in tree.body:
        if not isinstance(stmt, nodes.Output):
            problems.append(_reason("statement_not_allowed", line=stmt.lineno))
            continue
        problems.extend(p for n in stmt.nodes if (p := _check_output(n)) is not None)
    return problems


def validate_template(subject: str, body: str) -> None:
    """Validate subject and body of a user template.

    Raises:
        ValidationProblem: 422 `template_invalid` (or `subject_newline`) with `reasons[]`.
    """
    if "\r" in subject or "\n" in subject:
        raise ValidationProblem(
            "The subject must not contain line breaks.",
            code="subject_newline",
            extensions={"reasons": [_reason("subject_newline")]},
        )
    problems = [*find_problems(subject), *find_problems(body)]
    if len(subject) > SUBJECT_MAX:
        problems.append(_reason("subject_too_long", max=SUBJECT_MAX))
    if problems:
        raise ValidationProblem(
            "The mail template is invalid.",
            code="template_invalid",
            extensions={"reasons": problems},
        )


def render_template(subject: str, body: str, context: dict[str, dict[str, str]]) -> tuple[str, str]:
    """Validate and render subject and body (plain text).

    Raises:
        ValidationProblem: The template is invalid, or the render failed (never a 500).
    """
    validate_template(subject, body)
    try:
        rendered_subject = _ENV.from_string(subject).render(**context)
        rendered_body = _ENV.from_string(body).render(**context)
    except (TemplateError, TemplateRenderError) as exc:
        raise ValidationProblem(
            "The mail template could not be rendered.",
            code="template_invalid",
            extensions={"reasons": [_reason("render_error", message=str(exc))]},
        ) from exc
    if "\r" in rendered_subject or "\n" in rendered_subject:
        raise ValidationProblem(
            "The rendered subject must not contain line breaks.",
            code="subject_newline",
            extensions={"reasons": [_reason("subject_newline")]},
        )
    return rendered_subject, rendered_body
