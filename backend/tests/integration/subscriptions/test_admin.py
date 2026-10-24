"""Admin data request and erasure: rights, answers, audit entries without personal data."""

from __future__ import annotations

import pytest

from app.modules.subscriptions.admin_router import listmonk_finder
from app.modules.subscriptions.listmonk_port import ListmonkError, ListmonkSubscriber
from tests.integration.subscriptions.subs_harness import (
    SubsApi,
    api,
    clean_events,
    db_roles,
    subs,
    subs_url,
)

__fixtures__ = (api, clean_events, db_roles, subs, subs_url)
pytestmark = pytest.mark.integration
ADDRESS = "ada@example.org"
LOOKUP = "/api/admin/subscribers/lookup"
ERASE = "/api/admin/subscribers/erase"


def finder(result: ListmonkSubscriber | None, error: bool = False):  # noqa: ANN201
    async def find(canonical: str) -> ListmonkSubscriber | None:
        if error:
            raise ListmonkError("down")
        assert canonical == ADDRESS
        return result

    return lambda: find


async def ask(subs: SubsApi, user: str | None, path: str, email: str = ADDRESS):  # noqa: ANN201
    return await subs.api.request(user, "POST", path, json={"email": email})


async def test_only_the_privacy_right_may_ask(subs: SubsApi) -> None:
    assert (await ask(subs, None, LOOKUP)).status_code == 401
    for user in ("member", "editor", "organizer-fsi", "stupa"):
        assert (await ask(subs, user, LOOKUP)).status_code == 403, user
        assert (await ask(subs, user, ERASE)).status_code == 403, user
    assert (await ask(subs, "admin", LOOKUP)).status_code == 200


async def test_the_data_request_names_what_is_stored_without_the_address_or_a_token(
    subs: SubsApi,
) -> None:
    await subs.register(ADDRESS, interests=("party", "gaming"))
    await subs.sql(
        "INSERT INTO listmonk_list (key, listmonk_id, name) VALUES ('party', 7, 'events-party')"
    )
    subs.api.app.dependency_overrides[listmonk_finder] = finder(
        ListmonkSubscriber(id=3, email=ADDRESS, lists={7: "confirmed", 99: "confirmed"})
    )
    response = await ask(subs, "admin", LOOKUP, " Ada@Example.ORG ")
    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True and body["status"] == "confirmed"
    assert body["consentTextVersion"] == "2026-10-1"
    assert body["consentCategories"] == [
        "party",
        "campusfest",
        "festival",
        "get-together",
        "lanparty",
    ]
    assert body["profile"]["interests"] == ["party", "gaming"]
    assert body["profile"]["mailEnabled"] is True
    assert [o["op"] for o in body["outbox"]] == ["upsert"]
    assert body["listmonk"] == {"present": True, "lists": ["party"]}
    text = response.text
    assert (
        "ada@example" not in text.lower() and "TokenHash" not in text and "hash" not in text.lower()
    )


async def test_unknown_address_and_listmonk_trouble(subs: SubsApi) -> None:
    missing = await ask(subs, "admin", LOOKUP, "nobody@example.org")
    assert missing.status_code == 200 and missing.json()["found"] is False
    assert missing.json()["profile"] is None and missing.json()["listmonk"] is None
    await subs.register(ADDRESS)
    subs.api.app.dependency_overrides[listmonk_finder] = finder(None, error=True)
    assert (await ask(subs, "admin", LOOKUP)).json()["listmonk"] is None
    subs.api.app.dependency_overrides[listmonk_finder] = finder(None)
    assert (await ask(subs, "admin", LOOKUP)).json()["listmonk"] == {"present": False, "lists": []}
    assert (await ask(subs, "admin", LOOKUP, "kaputt")).status_code == 422


async def test_erasing_removes_the_data_and_audits_without_personal_data(subs: SubsApi) -> None:
    await subs.register(ADDRESS)
    assert (await ask(subs, "admin", ERASE)).status_code == 204
    assert await subs.scalar("SELECT status FROM subscriber") == "erased"
    assert await subs.scalar("SELECT count(*) FROM subscription_profile") == 0
    assert await subs.scalar("SELECT count(*) FROM outbox WHERE op = 'delete'") == 1
    again = await ask(subs, "admin", ERASE)
    assert again.status_code == 404
    entries = await subs.sql("SELECT actor, action, data FROM audit_entry ORDER BY id")
    kinds = [(e.action, e.data) for e in entries if e.action.startswith("subscriber.")]
    assert kinds == [("subscriber.erase", {"found": True}), ("subscriber.erase", {"found": False})]
    assert all(e.actor == "sub-admin" for e in entries if e.action.startswith("subscriber."))
    assert "example.org" not in str([tuple(e) for e in entries])
