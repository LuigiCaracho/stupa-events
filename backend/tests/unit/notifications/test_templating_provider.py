"""Sandboxed mail rendering, the kinds catalogue and the arq pool provider."""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.notifications import provider
from app.modules.notifications.kinds import NOTIFICATION_KINDS
from app.modules.notifications.templating import TemplateRenderError, render_mail


def test_render_resolves_language_with_german_fallback() -> None:
    mail = render_mail(
        subject_i18n={"de": "Hallo {{ name }}"},
        body_i18n={"de": "Text für {{ name }}"},
        body_html_i18n={"de": "<b>{{ name }}</b>"},
        context={"name": "<Ada>"},
        lang="en",
    )
    assert mail.subject == "Hallo <Ada>"
    assert mail.html == "<b>&lt;Ada&gt;</b>"
    assert mail.lang == "de"


def test_subject_loses_line_breaks() -> None:
    mail = render_mail(
        subject_i18n={"de": "A\r\nBcc: x@y.de"},
        body_i18n={"de": "b"},
        context={},
    )
    assert "\n" not in mail.subject and "\r" not in mail.subject


@pytest.mark.parametrize(
    ("subject", "body", "context"),
    [
        ({}, {"de": "b"}, {}),
        ({"de": "s"}, {}, {}),
        ({"de": "{{ missing }}"}, {"de": "b"}, {}),
        ({"de": "{% if %}"}, {"de": "b"}, {}),
        ({"de": "{{ ''.__class__.__mro__ }}"}, {"de": "b"}, {}),
    ],
)
def test_broken_or_hostile_templates_raise(
    subject: dict[str, str], body: dict[str, str], context: dict[str, object]
) -> None:
    with pytest.raises(TemplateRenderError):
        render_mail(subject_i18n=subject, body_i18n=body, context=context)


def test_kinds_m5b() -> None:
    assert set(NOTIFICATION_KINDS) == {"comment_added", "published", "cancelled", "checklist_due"}


async def test_pool_open_close_and_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, Any] = {}

    class Pool:
        closed = False

        async def aclose(self) -> None:
            self.closed = True

    async def create_pool(settings: Any, **kwargs: Any) -> Pool:
        created.update(kwargs)
        return Pool()

    monkeypatch.setattr("arq.create_pool", create_pool)
    pool = await provider.create_mail_pool("redis://x/0", "events")
    assert created["default_queue_name"] == "events"
    assert provider.mail_queue_from_pool(pool) is not None
    assert provider.mail_queue_from_pool(None) is None
    await provider.close_mail_pool(pool)
    assert pool is not None and pool.closed
    await provider.close_mail_pool(None)


async def test_pool_failure_is_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(*args: Any, **kwargs: Any) -> None:
        raise OSError("no redis")

    monkeypatch.setattr("arq.create_pool", boom)
    assert await provider.create_mail_pool("redis://x/0") is None
