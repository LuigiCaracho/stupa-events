"""The write path of `fire` maps a database check violation to `image_required`."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import DBAPIError

from app.modules.events.models import Event
from app.modules.pipeline.service import PipelineService
from app.modules.pipeline.transitions import TRANSITIONS
from app.shared.errors import ValidationProblem


class Session:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def execute(self, _statement: object) -> None:
        raise self.error


class Driver(Exception):
    def __init__(self, message: str, sqlstate: str | None, pgcode: str | None) -> None:
        super().__init__(message)
        self.sqlstate = sqlstate
        self.pgcode = pgcode


TRIGGER_MESSAGE = "event x cannot be approved without a valid poster or image exception"


def failure(
    sqlstate: str | None, pgcode: str | None = None, message: str = TRIGGER_MESSAGE
) -> DBAPIError:
    return DBAPIError("UPDATE", {}, Driver(message, sqlstate, pgcode))


@pytest.mark.parametrize("error", [failure("23514"), failure(None, "23514")])
async def test_check_violation_becomes_image_required(error: DBAPIError) -> None:
    service = PipelineService(Session(error))  # type: ignore[arg-type]
    with pytest.raises(ValidationProblem) as caught:
        await service._write(Event(), TRANSITIONS["T04"], {"state": "approved"})
    assert caught.value.code == "image_required"
    assert caught.value.extensions["reasons"][0]["fixAction"] is None  # type: ignore[index]


async def test_other_database_errors_are_not_swallowed() -> None:
    service = PipelineService(Session(failure("40001")))  # type: ignore[arg-type]
    with pytest.raises(DBAPIError):
        await service._write(Event(), TRANSITIONS["T04"], {"state": "approved"})


async def test_a_foreign_check_violation_is_not_reported_as_a_missing_image() -> None:
    service = PipelineService(Session(failure("23514", message="violates check ck_other")))  # type: ignore[arg-type]
    with pytest.raises(DBAPIError):
        await service._write(Event(), TRANSITIONS["T04"], {"state": "approved"})


async def test_a_missing_event_is_not_found_for_the_worker() -> None:
    from uuid import uuid4

    from app.shared.errors import NotFoundError

    class Empty:
        async def get(self, *_args: object) -> None:
            return None

    with pytest.raises(NotFoundError):
        await PipelineService(Empty()).stage_system_fire(uuid4(), "T05")  # type: ignore[arg-type]


async def test_other_status_event_errors_are_not_turned_into_four_eyes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.modules.events import revisions
    from tests.unit.pipeline.support import actor, snap

    async def revision(*_args: object, **_kwargs: object) -> None:
        return None

    async def fails(*_args: object, **_kwargs: object) -> None:
        raise failure("40001")

    monkeypatch.setattr(revisions, "append_revision", revision)
    monkeypatch.setattr(revisions, "append_status", fails)
    service = PipelineService(Session(failure("40001")))  # type: ignore[arg-type]
    with pytest.raises(DBAPIError):
        await service._record(  # noqa: SLF001
            SimpleNamespace(), TRANSITIONS["T04"], actor("editor"), snap(), None
        )
