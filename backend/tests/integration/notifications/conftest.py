"""Fixtures of the notification integration tests (tables come from migration 0005)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Principal
from app.modules.events.models import Event
from app.modules.orgs.models import Membership
from tests.integration.events.harness import Api, api, clean_events, db_roles  # noqa: F401

WIPE = "TRUNCATE notification, notification_pref, media_ref, markdown_image, comment, checklist_item CASCADE"


@pytest.fixture(autouse=True)
def m4_tables(engine: Engine, clean_events: None) -> Iterator[None]:  # noqa: F811
    with engine.begin() as conn:
        conn.execute(text(WIPE))
    yield
    with engine.begin() as conn:
        conn.execute(text(WIPE))


async def add_principal(
    session: AsyncSession, sub: str, groups: tuple[str, ...] = (), email: str | None = None
) -> Principal:
    row = Principal(sub=sub, email=email or f"{sub}@example.org", oidc_groups=list(groups))
    session.add(row)
    await session.flush()
    return row


async def add_member(session: AsyncSession, principal: Principal, org_id: str, role: str) -> None:
    session.add(Membership(principal_id=principal.id, organization_id=UUID(org_id), role=role))
    await session.flush()


async def load_event(session: AsyncSession, event_id: str) -> Event:
    return await session.get_one(Event, UUID(event_id))


async def add_checklist_item(
    session: AsyncSession, event_id: UUID, *, assignee: str | None, due_at: datetime | None
) -> UUID:
    item_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO checklist_item (id, event_id, position, text, phase, assignee_sub, due_at) "
            "VALUES (:id, :e, 'm', 'Plakat', 'planning', :a, :d)"
        ),
        {"id": item_id, "e": event_id, "a": assignee, "d": due_at},
    )
    return item_id


def utc(*args: Any) -> datetime:
    return datetime(*args, tzinfo=UTC)
