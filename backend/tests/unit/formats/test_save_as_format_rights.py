"""`save_as_format` refuses a reader who may neither manage formats nor submit for the organization."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.auth.principal import Principal
from app.modules.formats import service
from app.modules.formats.schemas import SaveAsFormatIn
from app.shared.errors import ForbiddenError


async def test_a_reader_without_submit_in_the_organization_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = SimpleNamespace(organization_id=uuid.uuid4(), format_id=None)

    async def readable(*_: Any) -> Any:
        return event

    monkeypatch.setattr(service, "load_readable", readable)
    reader = Principal(sub="s", roles=[], permissions=set())
    body = SaveAsFormatIn(slug="x-y", title="X")
    with pytest.raises(ForbiddenError):
        await service.save_as_format(None, reader, uuid.uuid4(), body)  # type: ignore[arg-type]
