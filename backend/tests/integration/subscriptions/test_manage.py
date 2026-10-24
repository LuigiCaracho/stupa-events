"""Magic link, the management routes, rotation and deletion."""

from __future__ import annotations

import re

import pytest

from app.modules.subscriptions.tokens import hash_token
from tests.integration.subscriptions.subs_harness import (
    SubsApi,
    api,
    clean_events,
    db_roles,
    link_of,
    subs,
    subs_url,
)

__fixtures__ = (api, clean_events, db_roles, subs, subs_url)
pytestmark = pytest.mark.integration
ADDRESS = "ada@example.org"
TOKEN_URL = re.compile(r"/ics/p/([A-Za-z0-9_-]{43})\.ics")


async def test_the_magic_link_goes_only_to_a_confirmed_address_and_always_answers_202(
    subs: SubsApi,
) -> None:
    await subs.subscribe(email="pending@example.org")
    subs.queue.sent.clear()
    await subs.register(ADDRESS)
    subs.queue.sent.clear()
    answers = [
        await subs.post("/api/public/subscriptions/manage-link", {"email": e, "altcha": ""})
        for e in ("unknown@example.org", "pending@example.org", ADDRESS)
    ]
    assert [r.status_code for r in answers] == [202, 202, 202]
    assert {r.content for r in answers} == {b"{}"}
    [message] = subs.queue.sent
    assert message.to == (ADDRESS,) and "Verwalten" in message.subject
    kind, token = link_of(message)
    assert kind == "abo" and f"https://events.example/abo/{token}" in message.text
    row = (
        await subs.sql(
            "SELECT manage_token_hash, manage_expires_at - now() AS ttl FROM subscriber WHERE status = 'confirmed'"
        )
    )[0]
    assert row.manage_token_hash == hash_token(token)
    assert 7000 < row.ttl.total_seconds() <= 7200


async def test_an_invalid_address_for_the_magic_link_is_a_422(subs: SubsApi) -> None:
    response = await subs.post(
        "/api/public/subscriptions/manage-link", {"email": "nope", "altcha": ""}
    )
    assert response.status_code == 422 and response.json()["code"] == "invalid_email"


async def test_me_shows_the_profile_and_never_the_calendar_address(subs: SubsApi) -> None:
    token = await subs.register(ADDRESS, interests=("party", "gaming"))
    response = await subs.me(token)
    assert response.status_code == 200 and "set-cookie" not in response.headers
    body = response.json()
    assert body["interests"] == ["party", "gaming"]
    assert [c["slug"] for c in body["categories"]][-1] == "lanparty"
    assert body["mailEnabled"] is True and body["hasProfile"] is True and body["icsUrl"] is None


async def test_every_wrong_management_token_gets_the_same_404(subs: SubsApi) -> None:
    token = await subs.register(ADDRESS)
    await subs.sql("UPDATE subscriber SET manage_expires_at = now() - interval '1 second'")
    other = await subs.api.client.request(
        "GET", f"/api/public/subscriptions/me?token={token}", headers={}
    )
    answers = [
        await subs.me(token),
        await subs.me("z" * 43),
        await subs.me("kurz"),
        other,
        await subs.api.client.get(
            "/api/public/subscriptions/me", headers={"X-Subscription-Token": ""}
        ),
    ]
    assert {r.status_code for r in answers} == {404}
    assert len({r.content for r in answers}) == 1
    assert answers[0].json()["code"] == "invalid_token"
    for method in ("PUT", "DELETE"):
        response = await subs.me(
            "z" * 43, method, **({"json": {"mailEnabled": False}} if method == "PUT" else {})
        )
        assert response.status_code == 404 and response.content == answers[0].content
    rotate = await subs.api.client.post(
        "/api/public/subscriptions/me/ics-token", headers={"X-Subscription-Token": "z" * 43}
    )
    assert rotate.status_code == 404 and rotate.content == answers[0].content


async def test_a_token_that_belongs_to_a_pending_address_is_not_a_management_token(
    subs: SubsApi,
) -> None:
    await subs.subscribe(email=ADDRESS)
    _, confirm_token = link_of(subs.queue.sent[-1])
    assert (await subs.me(confirm_token)).status_code == 404


async def test_changing_the_interests_rewrites_categories_consent_and_queues_an_upsert(
    subs: SubsApi,
) -> None:
    token = await subs.register(ADDRESS, interests=("party",))
    await subs.sql("UPDATE subscriber SET consent_text_version = 'old', consent_categories = '{}'")
    jobs = await subs.scalar("SELECT count(*) FROM outbox")
    wider = {"interests": ["kultur", "fachschaft:nxt"]}
    refused = await subs.me(token, "PUT", json=wider)
    assert refused.status_code == 422 and refused.json()["code"] == "consent_required"
    stale = {**wider, "consent": {"version": "old", "accepted": True}}
    assert (await subs.me(token, "PUT", json=stale)).status_code == 409
    assert await subs.scalar("SELECT count(*) FROM outbox") == jobs
    given = {"version": "2026-10-1", "accepted": True}
    response = await subs.me(token, "PUT", json={**wider, "consent": given})
    assert response.status_code == 200
    assert response.json()["interests"] == ["kultur", "fachschaft:nxt"]
    assert [c["slug"] for c in response.json()["categories"]] == [
        "kino",
        "konzert",
        "fachschaft-nxt",
    ]
    row = (await subs.sql("SELECT consent_text_version, consent_categories FROM subscriber"))[0]
    assert row.consent_text_version == "2026-10-1"
    assert row.consent_categories == ["kino", "konzert", "fachschaft-nxt"]
    assert await subs.scalar("SELECT count(*) FROM outbox") == jobs + 1
    assert (
        await subs.scalar("SELECT state FROM outbox ORDER BY created_at DESC LIMIT 1") == "pending"
    )


async def test_narrowing_the_interests_leaves_the_consent_proof_alone(subs: SubsApi) -> None:
    token = await subs.register(ADDRESS, interests=("party", "kultur"))
    before = (await subs.sql("SELECT consent_at, consent_categories FROM subscriber"))[0]
    response = await subs.me(token, "PUT", json={"interests": ["party"]})
    assert response.status_code == 200
    after = (await subs.sql("SELECT consent_at, consent_categories FROM subscriber"))[0]
    assert (after.consent_at, after.consent_categories) == (
        before.consent_at,
        before.consent_categories,
    )


async def test_the_mail_switch_and_bad_changes(subs: SubsApi) -> None:
    token = await subs.register(ADDRESS)
    off = await subs.me(token, "PUT", json={"mailEnabled": False})
    assert off.status_code == 200 and off.json()["mailEnabled"] is False
    assert (
        await subs.scalar(
            "SELECT mail_enabled FROM subscription_profile WHERE subscriber_id IS NOT NULL"
        )
        is False
    )
    assert await subs.scalar("SELECT status FROM subscriber") == "confirmed"
    for body, code in (
        ({}, "validation_error"),
        ({"interests": []}, "no_interest"),
        ({"interests": ["unsinn"]}, "unknown_interest"),
    ):
        response = await subs.me(token, "PUT", json=body)
        assert response.status_code == 422 and response.json()["code"] == code
    assert (await subs.me(token, "PUT", json={"nope": 1})).status_code == 422


async def test_rotation_shows_the_new_address_once_and_invalidates_the_old_token(
    subs: SubsApi,
) -> None:
    created = await subs.subscribe(email=ADDRESS)
    old = TOKEN_URL.search(created.json()["profile"]["icsUrl"])
    assert old is not None
    _, confirm = link_of(subs.queue.sent[-1])
    await subs.confirm(confirm)
    manage = await subs.manage_token(ADDRESS)
    response = await subs.api.client.post(
        "/api/public/subscriptions/me/ics-token", headers={"X-Subscription-Token": manage}
    )
    assert response.status_code == 200 and "set-cookie" not in response.headers
    fresh = TOKEN_URL.search(response.json()["icsUrl"])
    assert fresh is not None and fresh[1] != old[1]
    assert response.json()["webcalUrl"].startswith("webcal://")
    hashes = await subs.sql("SELECT ics_token_hash FROM subscription_profile")
    assert [h[0] for h in hashes] == [hash_token(fresh[1])]
    assert (await subs.api.client.get(f"/ics/p/{old[1]}.ics")).status_code == 404
    assert (await subs.api.client.get(f"/ics/p/{fresh[1]}.ics")).status_code == 200


async def test_deleting_removes_address_profile_tokens_and_leaves_a_clean_tombstone(
    subs: SubsApi,
) -> None:
    created = await subs.subscribe(email=ADDRESS)
    ics = TOKEN_URL.search(created.json()["profile"]["icsUrl"])
    assert ics is not None
    _, confirm = link_of(subs.queue.sent[-1])
    await subs.confirm(confirm)
    manage = await subs.manage_token(ADDRESS)
    assert (await subs.me(manage, "DELETE")).status_code == 204
    assert (await subs.me(manage)).status_code == 404
    assert (await subs.api.client.get(f"/ics/p/{ics[1]}.ics")).status_code == 404
    assert await subs.scalar("SELECT count(*) FROM subscription_profile") == 0
    [row] = await subs.sql("SELECT * FROM subscriber")
    data = row._asdict()
    assert data["status"] == "erased"
    for column in (
        "email_enc",
        "email_hmac",
        "confirm_token_hash",
        "manage_token_hash",
        "listmonk_subscriber_id",
    ):
        assert data[column] is None, column
    assert data["consent_categories"] == []
    assert ADDRESS not in str(data) and manage not in str(data)
    [job] = await subs.sql("SELECT op, state, payload FROM outbox WHERE op = 'delete'")
    assert job.state == "pending" and job.payload["emailEnc"]
    [block] = await subs.sql("SELECT state, payload FROM outbox WHERE op = 'unsubscribe'")
    assert block.state == "pending" and block.payload["emailEnc"]
    states = {
        r.state
        for r in await subs.sql(
            "SELECT state FROM outbox WHERE op NOT IN ('delete', 'unsubscribe')"
        )
    }
    assert states <= {"done"}
    again = await subs.subscribe(email=ADDRESS)
    assert again.status_code == 202 and link_of(subs.queue.sent[-1])[0] == "bestaetigen"


async def test_the_management_routes_without_keys_are_a_503(subs: SubsApi) -> None:
    subs.configure(pgcrypto_email_key=None, email_hash_key=None)
    response = await subs.subscribe(email=ADDRESS)
    assert response.status_code == 503
    assert (await subs.me("z" * 43, "DELETE")).status_code == 503
