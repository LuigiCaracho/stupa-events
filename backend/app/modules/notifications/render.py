"""Render the system mails of the notification kinds from `templates/de/<kind>.*.j2`.

Jinja sandbox with `StrictUndefined`; HTML autoescapes. The subject never carries CR or LF.
German only (`mail_default_lang = de`). Links are absolute, built from `public_base_url`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment

from app.modules.notifications.templating import TemplateRenderError

TEMPLATE_DIR = Path(__file__).parent / "templates" / "de"
_text = SandboxedEnvironment(
    undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True
)
_html = SandboxedEnvironment(undefined=StrictUndefined, autoescape=True, keep_trailing_newline=True)


def absolute_link(base_url: str, link: str) -> str:
    """Join the public base URL and a site-relative link."""
    return f"{base_url.rstrip('/')}{link}"


def _render(kind: str, part: str, ctx: Mapping[str, object], *, html: bool) -> str:
    source = (TEMPLATE_DIR / f"{kind}.{part}.j2").read_text(encoding="utf-8")
    try:
        return (_html if html else _text).from_string(source).render(**ctx)
    except TemplateError as exc:
        raise TemplateRenderError(str(exc)) from exc


def render_system_mail(kind: str, ctx: Mapping[str, object]) -> tuple[str, str, str]:
    """Render subject, plain text and HTML of a mail kind.

    Raises:
        TemplateRenderError: A placeholder is missing or the template is broken.
    """
    subject = " ".join(_render(kind, "subject", ctx, html=False).splitlines()).strip()
    return subject, _render(kind, "txt", ctx, html=False), _render(kind, "html", ctx, html=True)
