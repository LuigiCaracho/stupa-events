"""System mail rendering and the post-commit dispatch (no Redis -> drop with a warning)."""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from app.modules.notifications.kinds import KINDS, Kind
from app.modules.notifications.mail import MailMessage
from app.modules.notifications.render import absolute_link, render_system_mail
from app.modules.notifications.service import PendingMail, _switch, dispatch_mails, event_link
from app.modules.notifications.templating import TemplateRenderError

_CTX = {
    "title": "Fest <b>",
    "actor": "Ada",
    "item": "Plakat",
    "due": "05.07.2026",
    "link": "https://x.test/dossiers/1",
    "prefs_link": "https://x.test/konto",
}


@pytest.mark.parametrize("kind", [k.key for k in KINDS if k.mail])
def test_every_mail_kind_renders(kind: str) -> None:
    subject, text, html = render_system_mail(kind, _CTX)
    assert subject
    assert "\n" not in subject
    assert "https://x.test/dossiers/1" in text
    assert "&lt;b&gt;" in html


def test_missing_variable_fails_loudly() -> None:
    with pytest.raises(TemplateRenderError):
        render_system_mail("comment_added", {"title": "x"})


def test_links() -> None:
    assert absolute_link("https://x.test/", "/konto") == "https://x.test/konto"
    eid = uuid4()
    assert event_link("comment_added", eid) == f"/dossiers/{eid}#verlauf"
    assert event_link("checklist_due", eid) == f"/dossiers/{eid}#checkliste"
    assert event_link("published", eid) == f"/dossiers/{eid}"


class _Pref:
    def __init__(self, in_app: bool, mail: bool) -> None:
        self.in_app, self.mail = in_app, mail


def test_prefs_respected_and_essential_forced() -> None:
    comment = next(k for k in KINDS if k.key == "comment_added")
    essential = Kind("fixed", mail=True, essential=True)
    resolved = Kind("quiet", mail=False)
    assert _switch(comment, None) == (True, True)
    assert _switch(comment, _Pref(False, True)) == (False, True)  # type: ignore[arg-type]
    assert _switch(comment, _Pref(True, False)) == (True, False)  # type: ignore[arg-type]
    assert _switch(essential, _Pref(False, False)) == (True, True)  # type: ignore[arg-type]
    assert _switch(resolved, _Pref(True, True)) == (True, False)  # type: ignore[arg-type]


class _Pool:
    def __init__(self) -> None:
        self.claimed: set[str] = set()
        self.jobs: list[tuple[str, object, dict[str, object]]] = []

    async def set(
        self, key: str, value: str, nx: bool = False, ex: int | None = None
    ) -> bool | None:
        if key in self.claimed:
            return None
        self.claimed.add(key)
        return True

    async def delete(self, key: str) -> None:
        self.claimed.discard(key)

    async def enqueue_job(self, name: str, payload: object, **kw: object) -> object:
        self.jobs.append((name, payload, kw))
        return object()


def _pending() -> PendingMail:
    msg = MailMessage(to=("secret@x.de",), subject="S", text="b", idempotency_key="mail:k")
    return PendingMail(uuid4(), msg)


async def test_dispatch_claims_once_and_enqueues() -> None:
    pool, item = _Pool(), _pending()
    await dispatch_mails(pool, [item])
    await dispatch_mails(pool, [item])
    assert [j[0] for j in pool.jobs] == ["send_mail"]
    assert f"notif:{item.notification_id}:mail" in pool.claimed


async def test_dispatch_without_pool_drops_without_address(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.mail"):
        await dispatch_mails(None, [_pending()])
    assert "mail dropped" in caplog.text
    assert "secret@x.de" not in caplog.text


async def test_dispatch_swallows_redis_errors(caplog: pytest.LogCaptureFixture) -> None:
    class Broken(_Pool):
        async def set(self, *a: object, **k: object) -> bool:  # type: ignore[override]
            raise ConnectionError("down")

    with caplog.at_level(logging.WARNING, logger="app.mail"):
        await dispatch_mails(Broken(), [_pending()])
    assert "secret@x.de" not in caplog.text


async def test_a_failed_enqueue_releases_the_claim_so_a_retry_can_send() -> None:
    class Flaky(_Pool):
        fail = True

        async def enqueue_job(self, name: str, payload: object, **kw: object) -> object:
            if self.fail:
                raise ConnectionError("down")
            return await super().enqueue_job(name, payload, **kw)

    pool, item = Flaky(), _pending()
    await dispatch_mails(pool, [item])
    assert not pool.claimed
    pool.fail = False
    await dispatch_mails(pool, [item])
    assert [j[0] for j in pool.jobs] == ["send_mail"]
