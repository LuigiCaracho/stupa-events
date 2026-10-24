"""Questionnaire, sign-up and the double opt-in against a real database and the subs role."""

from __future__ import annotations

import re
from typing import Any

import pytest

from app.modules.subscriptions.emailkey import identity_hmac
from app.modules.subscriptions.tokens import hash_token
from tests.integration.subscriptions.subs_harness import (
    HASH_KEY,
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
TOKEN_URL = re.compile(r"/ics/p/([A-Za-z0-9_-]{43})\.ics")


def normalized(body: dict[str, Any]) -> dict[str, Any]:
    """The answer without the calendar token, which is fresh every time."""
    out = {**body, "profile": {**body["profile"]}}
    out["profile"]["icsUrl"] = TOKEN_URL.sub("/ics/p/TOKEN.ics", out["profile"]["icsUrl"])
    out["profile"]["webcalUrl"] = TOKEN_URL.sub("/ics/p/TOKEN.ics", out["profile"]["webcalUrl"])
    return out


async def test_the_questionnaire_has_five_questions_the_consent_and_no_cookie(
    subs: SubsApi,
) -> None:
    response = await subs.api.client.get("/api/public/getstarted/questions")
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert response.headers["cache-control"] == "public, max-age=300"
    body = response.json()
    assert [q["id"] for q in body["questions"]] == [
        "interests",
        "meetings",
        "faculty",
        "channel",
        "mail",
    ]
    interests = {o["value"]: o["label"] for o in body["questions"][0]["options"]}
    assert {"party", "kultur", "sport", "gaming", "lernen", "sitzung"} == set(interests)
    faculty = {o["value"] for o in body["questions"][2]["options"]}
    assert "fachschaft:informatik-fsi" in faculty and "fachschaft:esb-stuco" in faculty
    assert "fachschaft:nxt" in faculty and "fachschaft" not in faculty
    assert body["consent"] == {
        "version": "2026-10-1",
        "template": (
            "Ich möchte wöchentlich eine Mail zu {categories}. "
            "Abmelden geht jederzeit mit einem Klick."
        ),
        "privacyUrl": "/datenschutz",
    }
    again = await subs.api.client.get(
        "/api/public/getstarted/questions", headers={"If-None-Match": response.headers["etag"]}
    )
    assert again.status_code == 304


async def test_a_calendar_only_profile_has_the_party_categories_and_no_meeting(
    subs: SubsApi,
) -> None:
    response = await subs.subscribe(interests=("party",))
    assert response.status_code == 202
    assert "set-cookie" not in response.headers and "no-store" in response.headers["cache-control"]
    body = response.json()
    assert body["mail"] == {"requested": False}
    slugs = [c["slug"] for c in body["profile"]["categories"]]
    assert slugs == ["party", "campusfest", "festival", "get-together"]
    token = TOKEN_URL.search(body["profile"]["icsUrl"])
    assert token is not None
    assert body["profile"]["webcalUrl"].startswith("webcal://events.example/ics/p/")
    assert subs.queue.sent == []
    assert await subs.scalar("SELECT count(*) FROM subscriber") == 0
    row = (
        await subs.sql("SELECT ics_token_hash, categories, mail_enabled FROM subscription_profile")
    )[0]
    assert row.ics_token_hash == hash_token(token[1]) and row.mail_enabled is False
    dump = str(await subs.sql("SELECT * FROM subscription_profile"))
    assert token[1] not in dump


async def test_the_meetings_and_faculty_answers_extend_the_profile(subs: SubsApi) -> None:
    body = (
        await subs.subscribe(interests=("kultur",), meetings=True, faculty="fachschaft:technik-tec")
    ).json()
    slugs = [c["slug"] for c in body["profile"]["categories"]]
    assert slugs == ["kino", "konzert", "sitzung", "fachschaft-technik-tec"]
    stored = (await subs.sql("SELECT interests FROM subscription_profile"))[0][0]
    assert stored == ["kultur", "sitzung", "fachschaft:technik-tec"]


async def test_sign_up_with_mail_queues_the_confirmation_and_stores_no_clear_address(
    subs: SubsApi,
) -> None:
    response = await subs.subscribe(email="Ada.Lovelace@Example.org")
    assert response.status_code == 202 and response.json()["mail"] == {"requested": True}
    [message] = subs.queue.sent
    assert message.to == ("ada.lovelace@example.org",)
    assert message.subject == "Bitte bestätige dein Abo bei STUPA Events"
    kind, token = link_of(message)
    assert kind == "bestaetigen"
    assert f"https://events.example/bestaetigen/{token}" in message.text
    assert "Partys und Feiern" in message.text and "24 Stunden" in message.text
    row = (
        await subs.sql(
            "SELECT status, confirm_token_hash, consent_text_version, consent_categories, "
            "email_enc IS NOT NULL AS has_enc, mails_count FROM subscriber"
        )
    )[0]
    assert row.status == "pending" and row.confirm_token_hash == hash_token(token)
    assert row.consent_text_version == "2026-10-1" and row.has_enc and row.mails_count == 1
    assert row.consent_categories == ["party", "campusfest", "festival", "get-together"]
    everything = str(await subs.sql("SELECT * FROM subscriber")) + str(
        await subs.sql("SELECT * FROM subscription_profile")
    )
    assert "ada.lovelace" not in everything.lower() and token not in everything
    assert (
        await subs.scalar(
            "SELECT count(*) FROM subscription_profile WHERE subscriber_id IS NOT NULL"
        )
        == 1
    )
    decrypted = await subs.scalar(
        "SELECT pgp_sym_decrypt(email_enc, :k) FROM subscriber", k="p" * 32
    )
    assert decrypted == "ada.lovelace@example.org"


async def test_the_preview_changes_nothing_and_the_post_confirms_exactly_once(
    subs: SubsApi,
) -> None:
    await subs.subscribe(email="ada@example.org", interests=("party", "gaming"))
    _, token = link_of(subs.queue.sent[-1])
    preview = await subs.post("/api/public/subscriptions/confirm/preview", {"token": token})
    assert preview.status_code == 200
    assert preview.json() == {"categories": ["Partys und Feiern", "Gaming und LAN"]}
    get = await subs.api.client.get("/api/public/subscriptions/confirm")
    assert get.status_code == 405
    assert await subs.scalar("SELECT status FROM subscriber") == "pending"
    assert await subs.scalar("SELECT count(*) FROM outbox") == 0
    done = await subs.confirm(token)
    assert done.status_code == 200 and done.json() == {"status": "confirmed"}
    row = (await subs.sql("SELECT status, confirmed_at, confirm_token_hash FROM subscriber"))[0]
    assert row.status == "confirmed" and row.confirmed_at is not None
    assert row.confirm_token_hash is None
    assert await subs.scalar("SELECT mail_enabled FROM subscription_profile") is True
    [job] = await subs.sql("SELECT op, state, payload FROM outbox")
    assert (job.op, job.state, job.payload) == ("upsert", "pending", {})
    assert (await subs.confirm(token)).status_code == 404
    assert await subs.scalar("SELECT count(*) FROM outbox") == 1


async def test_every_bad_token_gets_the_same_404(subs: SubsApi) -> None:
    await subs.subscribe(email="ada@example.org")
    _, token = link_of(subs.queue.sent[-1])
    await subs.sql("UPDATE subscriber SET confirm_expires_at = now() - interval '1 minute'")
    answers = [
        await subs.confirm(token),
        await subs.confirm("x" * 43),
        await subs.confirm("kurz"),
        await subs.post("/api/public/subscriptions/confirm/preview", {"token": token}),
        await subs.post("/api/public/subscriptions/confirm/preview", {"token": "y" * 43}),
    ]
    assert {r.status_code for r in answers} == {404}
    assert len({r.content for r in answers}) == 1
    assert answers[0].json()["code"] == "invalid_token"
    assert "traceId" not in answers[0].json()
    assert answers[0].headers["content-type"].startswith("application/problem+json")
    assert await subs.scalar("SELECT status FROM subscriber") == "pending"


@pytest.mark.parametrize(
    "state", ["unknown", "pending", "confirmed", "unsubscribed", "bounced", "erased"]
)
async def test_every_address_state_gets_the_same_answer(subs: SubsApi, state: str) -> None:
    address = "ada@example.org"
    reference = await subs.subscribe(interests=("kultur",), email="someone-else@example.org")
    subs.queue.sent.clear()
    if state != "unknown":
        await subs.subscribe(email=address)
        _, token = link_of(subs.queue.sent[-1])
        if state != "pending":
            await subs.confirm(token)
        if state in {"unsubscribed", "bounced"}:
            await subs.sql(
                "UPDATE subscriber SET status = :s, unsubscribed_at = now() WHERE email_hmac = :h",
                s=state,
                h=identity_hmac(HASH_KEY, address),
            )
        if state == "erased":
            sid = await subs.scalar(
                "SELECT id FROM subscriber WHERE email_hmac = :h",
                h=identity_hmac(HASH_KEY, address),
            )
            await subs.sql("SELECT privacy_erase_subscriber(:id)", id=sid)
        subs.queue.sent.clear()
    response = await subs.subscribe(interests=("kultur",), email=address)
    assert response.status_code == 202
    assert normalized(response.json()) == normalized(reference.json())
    [message] = subs.queue.sent
    kind, _ = link_of(message)
    assert kind == ("abo" if state == "confirmed" else "bestaetigen")
    assert (message.subject == "Du bist schon bei STUPA Events angemeldet") is (
        state == "confirmed"
    )


async def test_a_known_address_keeps_its_interests_and_lists(subs: SubsApi) -> None:
    await subs.register("ada@example.org", interests=("party",))
    before = await subs.sql(
        "SELECT categories, updated_at FROM subscription_profile WHERE mail_enabled"
    )
    jobs = await subs.scalar("SELECT count(*) FROM outbox")
    again = await subs.subscribe(interests=("sport", "gaming"), email="ada@example.org")
    assert again.status_code == 202
    assert (
        await subs.sql("SELECT categories, updated_at FROM subscription_profile WHERE mail_enabled")
        == before
    )
    assert await subs.scalar("SELECT count(*) FROM outbox") == jobs
    assert await subs.scalar("SELECT status FROM subscriber") == "confirmed"
    assert await subs.scalar("SELECT count(*) FROM subscription_profile") == 2
    assert (
        await subs.scalar("SELECT count(*) FROM subscription_profile WHERE subscriber_id IS NULL")
        == 1
    )


async def test_signing_up_again_after_unsubscribing_needs_a_new_confirmation(
    subs: SubsApi,
) -> None:
    await subs.register("ada@example.org")
    await subs.sql("UPDATE subscriber SET status = 'unsubscribed', unsubscribed_at = now()")
    await subs.sql("UPDATE subscription_profile SET mail_enabled = false")
    await subs.subscribe(email="ada@example.org", interests=("gaming",))
    _, token = link_of(subs.queue.sent[-1])
    assert await subs.scalar("SELECT status FROM subscriber") == "unsubscribed"
    assert await subs.scalar("SELECT count(*) FROM subscription_profile WHERE mail_enabled") == 0
    assert (await subs.confirm(token)).status_code == 200
    row = (await subs.sql("SELECT status, unsubscribed_at FROM subscriber"))[0]
    assert row.status == "confirmed" and row.unsubscribed_at is None
    payload = (
        await subs.sql("SELECT payload FROM outbox WHERE op = 'upsert' ORDER BY created_at DESC")
    )[0][0]
    assert payload == {"reconfirmed": True}
    assert await subs.scalar("SELECT categories FROM subscription_profile WHERE mail_enabled") == [
        "lanparty"
    ]


@pytest.mark.parametrize(
    ("over", "status", "code"),
    [
        ({"interests": ("party", "unsinn")}, 422, "unknown_interest"),
        ({"interests": ()}, 422, "no_interest"),
        ({"faculty": "fachschaft:gibts-nicht"}, 422, "unknown_interest"),
        ({"email": "keine-adresse"}, 422, "invalid_email"),
        ({"email": "a@example.org", "consent": False}, 422, "consent_required"),
        ({"questionnaire_version": 2}, 409, "questionnaire_outdated"),
    ],
)
async def test_bad_answers_are_refused_with_a_code(
    subs: SubsApi, over: dict[str, Any], status: int, code: str
) -> None:
    version = over.pop("questionnaire_version", 1)
    body = subs.signup(**over)
    body["questionnaireVersion"] = version
    response = await subs.post("/api/public/subscriptions", body)
    assert response.status_code == status and response.json()["code"] == code
    assert await subs.scalar("SELECT count(*) FROM subscription_profile") == 0


async def test_the_consent_version_must_be_the_current_one(subs: SubsApi) -> None:
    body = subs.signup(email="a@example.org")
    body["consent"]["version"] = "2020-01-1"
    response = await subs.post("/api/public/subscriptions", body)
    assert response.status_code == 409 and response.json()["code"] == "consent_outdated"
    assert await subs.scalar("SELECT count(*) FROM subscriber") == 0


async def test_mail_needs_address_and_consent_and_no_mail_forbids_them(subs: SubsApi) -> None:
    body = subs.signup(email="a@example.org")
    body["email"] = None
    assert (await subs.post("/api/public/subscriptions", body)).status_code == 422
    body = subs.signup()
    body["email"] = "a@example.org"
    assert (await subs.post("/api/public/subscriptions", body)).status_code == 422
    body = subs.signup()
    body["unknown"] = 1
    assert (await subs.post("/api/public/subscriptions", body)).status_code == 422


async def test_the_confirmation_of_a_later_attempt_replaces_the_earlier_token(
    subs: SubsApi,
) -> None:
    await subs.subscribe(email="ada@example.org")
    _, first = link_of(subs.queue.sent[-1])
    await subs.subscribe(email="ada@example.org")
    _, second = link_of(subs.queue.sent[-1])
    assert first != second
    assert (await subs.confirm(first)).status_code == 404
    assert (await subs.confirm(second)).status_code == 200
    assert await subs.scalar("SELECT count(*) FROM subscriber") == 1
