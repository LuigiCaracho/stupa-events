"""Recipient rules against real memberships, and mails that only leave with Redis."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text

from app.modules.notifications.mail import CapturingMailSender
from app.modules.notifications.recipients import recipients_for
from app.modules.notifications.service import dispatch_mails, notify, notify_event
from app.settings import load_settings
from tests.integration.events.harness import Api
from tests.integration.notifications.conftest import (
    add_checklist_item,
    add_member,
    add_principal,
    load_event,
)
from worker.mail import send_mail

pytestmark = pytest.mark.integration


async def _people(api: Api, session: Any) -> None:
    fsi = api.org_ids["fsi"]
    await add_principal(session, "sub-editor", ("events-editor",))
    await add_principal(session, "sub-editor-2", ("events-editor",))
    await add_principal(session, "sub-stranger", ("events-stupa",))
    organizer = await add_principal(session, "sub-org-fsi")
    submitter = await add_principal(session, "sub-sub-fsi")
    await add_member(session, organizer, fsi, "organizer")
    await add_member(session, submitter, fsi, "submitter")
    other = await add_principal(session, "sub-org-makers")
    await add_member(session, other, api.org_ids["makers"], "organizer")


async def test_notification_fanout(api: Api) -> None:
    event = await api.create_event()
    async with api.maker() as session:
        await _people(api, session)
        row = await load_event(session, event["id"])
        who = lambda kind, actor=None: recipients_for(session, kind, row, actor)  # noqa: E731
        published = set(await who("published"))
        assert published >= {"sub-editor", "sub-editor-2", "sub-org-fsi", "sub-sub-fsi"}
        assert "sub-stranger" not in published and "sub-org-makers" not in published
        assert set(await who("cancelled")) >= {row.created_by, "sub-org-fsi"}
        assert set(await who("comment_added")) >= {"sub-org-fsi", row.created_by}
        assert "sub-org-makers" not in await who("comment_added")
        assert row.created_by not in await who("published", row.created_by)


async def test_recipients_without_organization(api: Api) -> None:
    event = await api.create_event()
    async with api.maker() as session:
        await _people(api, session)
        row = await load_event(session, event["id"])
        row.organization_id = None
        assert set(await recipients_for(session, "published", row, None)) == {
            "sub-editor",
            "sub-editor-2",
        }


async def test_commenters_are_recipients(api: Api) -> None:
    event = await api.create_event()
    async with api.maker() as session:
        await _people(api, session)
        row = await load_event(session, event["id"])
        await session.execute(
            text(
                "INSERT INTO comment (event_id, author_sub, body_md) VALUES (:e, 'sub-stupa', 'x')"
            ),
            {"e": row.id},
        )
        subs = await recipients_for(session, "comment_added", row, "sub-stupa")
        assert "sub-stupa" not in subs
        await session.execute(
            text(
                "INSERT INTO comment (event_id, author_sub, body_md) VALUES (:e, 'sub-editor-2', 'x')"
            ),
            {"e": row.id},
        )
        assert "sub-editor-2" in await recipients_for(session, "comment_added", row, "sub-stupa")


async def test_mail_requires_redis(api: Api, caplog: pytest.LogCaptureFixture) -> None:
    event = await api.create_event()
    async with api.maker() as session:
        await add_principal(session, "sub-editor", ("events-editor",), "lena@example.org")
        row = await load_event(session, event["id"])
        pending = await notify_event(
            session, "published", row, {"actorName": "Ada"}, actor_sub="sub-someone"
        )
        await session.commit()
    assert len(pending) == 1
    msg = pending[0].message
    assert msg.to == ("lena@example.org",)
    assert msg.idempotency_key.startswith("mail:")
    assert row.title in msg.subject or row.title in msg.text
    assert f"/dossiers/{row.id}" in msg.text

    with caplog.at_level(logging.WARNING, logger="app.mail"):
        await dispatch_mails(None, pending)
    assert "lena@example.org" not in caplog.text
    assert (await api.sql("SELECT count(*) FROM notification"))[0][0] == 1

    await dispatch_mails(api.pool, pending)
    await dispatch_mails(api.pool, pending)
    jobs = [j for j in api.pool.jobs if j[0] == "send_mail"]
    assert len(jobs) == 1
    sender = CapturingMailSender()
    ctx = {"settings": load_settings(), "mail_sender": sender}
    assert await send_mail(ctx, jobs[0][1][0]) == "sent"
    assert sender.sent[0].to == ("lena@example.org",)


async def test_actor_gets_nothing_and_no_email_means_no_mail(api: Api) -> None:
    event = await api.create_event()
    async with api.maker() as session:
        await add_principal(session, "sub-a", email=None)
        row = await load_event(session, event["id"])
        await session.execute(text("UPDATE principal SET email = NULL WHERE sub = 'sub-a'"))
        pending = await notify(
            session,
            "comment_added",
            ["sub-a", "sub-me"],
            row,
            {"actorName": "Ada"},
            None,
            actor_sub="sub-me",
        )
        await session.commit()
    assert pending == []
    assert (await api.sql("SELECT recipient_sub FROM notification")) == [("sub-a",)]


async def test_due_reminder_cron_idempotent(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime

    import worker.mail as worker_mail

    monkeypatch.setattr(worker_mail, "utcnow", lambda: datetime(2026, 7, 1, 8, 10, tzinfo=UTC))
    event = await api.create_event()
    async with api.maker() as session:
        await add_principal(session, "sub-assignee", email="who@example.org")
        due = datetime(2026, 7, 2, 7, 0, tzinfo=UTC)
        later = datetime(2026, 7, 5, 7, 0, tzinfo=UTC)
        item = await add_checklist_item(
            session, UUID(event["id"]), assignee="sub-assignee", due_at=due
        )
        await add_checklist_item(session, UUID(event["id"]), assignee="sub-assignee", due_at=later)
        await add_checklist_item(session, UUID(event["id"]), assignee=None, due_at=due)
        await session.commit()
    ctx: dict[str, Any] = {"mail_sessionmaker": api.maker, "redis": api.pool}
    assert "items=1 mails=1" in await worker_mail.send_due_reminders(ctx)
    assert "items=0 mails=0" in await worker_mail.send_due_reminders(ctx)
    assert len([j for j in api.pool.jobs if j[0] == "send_mail"]) == 1
    rows = await api.sql("SELECT kind, dedupe_key FROM notification")
    assert rows == [("checklist_due", f"checklist_due:{item}:2026-07-02:sub-assignee")]

    await api.sql(
        "UPDATE checklist_item SET due_at = :d WHERE id = :i",
        d=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
        i=item,
    )
    assert "items=0" in await worker_mail.send_due_reminders(ctx)
    await api.sql("UPDATE checklist_item SET done_at = now() WHERE id = :i", i=item)
    assert "items=0" in await worker_mail.send_due_reminders(ctx)
