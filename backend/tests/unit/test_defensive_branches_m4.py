"""Defensive branches the API never reaches with valid callers: they stay correct on their own.

The upload and patch routes check consent and image kinds before these helpers run, and the
database refuses what slips through; the helpers are still tested directly so that
`coverage_critical` keeps `files/*` and `notifications/service` at 100 % (M4 contract 9).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError

from app.modules.dossier import comments
from app.modules.dossier.schemas_comments import CommentCreate
from app.modules.files import attachments, mime
from app.modules.notifications import service
from app.modules.notifications.templating import TemplateRenderError
from app.shared.errors import ForbiddenError, ValidationProblem
from tests._support.factories import make_principal, make_settings


def test_missing_rights_names_the_consent_note() -> None:
    row = attachments.NewAttachment(
        kind="social_post",
        filename="a.png",
        data=b"",
        alt_text="Bild",
        credit="Ada",
        rights_basis="own_work",
        persons_depicted=True,
    )
    assert attachments.missing_rights(row) == ["consentNote"]


def test_a_planned_social_post_needs_an_image() -> None:
    with pytest.raises(ValidationProblem) as caught:
        attachments._check_social("social_post", {"status": "planned"}, "application/pdf", [])  # pyright: ignore[reportPrivateUsage]
    assert caught.value.code == "social_post_needs_image"


def test_only_ooxml_extensions_count_as_containers() -> None:
    assert mime._is_ooxml_container(b"PK", ".odt") is False  # pyright: ignore[reportPrivateUsage]


class _FailingSession:
    def __init__(self, message: str) -> None:
        self.message = message

    async def flush(self) -> None:
        raise DBAPIError("UPDATE attachment", {}, Exception(self.message))


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("ck_attachment_restricted_not_shared", ValidationProblem),
        ("something else", DBAPIError),
    ],
)
async def test_flush_maps_the_database_nets(message: str, expected: type[Exception]) -> None:
    with pytest.raises(expected):
        await attachments._flush_or_conflict(_FailingSession(message))  # pyright: ignore[reportPrivateUsage, reportArgumentType]


def test_a_broken_template_skips_only_that_mail(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(kind: str, ctx: dict[str, Any]) -> tuple[str, str, str]:
        raise TemplateRenderError("boom")

    monkeypatch.setattr(service, "render_system_mail", broken)
    with caplog.at_level(logging.ERROR):
        built = service._build_mail(  # pyright: ignore[reportPrivateUsage]
            "comment_added", uuid4(), "a@example.org", {}, "/x", make_settings()
        )
    assert built is None and "mail render failed" in caplog.text


async def test_a_reader_without_comment_write_in_the_organization_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Event:
        id = uuid4()
        organization_id = uuid4()

    async def readable(*_: object) -> _Event:
        return _Event()

    monkeypatch.setattr(comments, "load_readable", readable)
    with pytest.raises(ForbiddenError):
        await comments.create(None, make_principal(), uuid4(), CommentCreate(body_md="Frage"))  # pyright: ignore[reportArgumentType]


async def test_a_rescan_needs_the_approve_right_in_the_organization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Event:
        organization_id = uuid4()

    async def loaded(*_: object) -> tuple[object, _Event]:
        return object(), _Event()

    monkeypatch.setattr(attachments, "load_attachment", loaded)
    with pytest.raises(ForbiddenError):
        await attachments.request_rescan(None, make_principal(), uuid4())  # pyright: ignore[reportArgumentType]
