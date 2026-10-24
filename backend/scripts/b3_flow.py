"""B3 acceptance, public flow: profile calendar, double opt-in, equal answers, rotation.

Item a: "only parties, no meetings" gives a profile whose calendar holds only party events and
a Listmonk subscriber on exactly the party lists. Item b: a GET on the confirmation link (API
shell and `ng serve`) changes nothing, the POST button confirms once. Item c: known and unknown
addresses get the same status, the same body (tokens masked) and the same answer time, ten
rounds each. Item d (B2): a rotated calendar token answers the same 404 as an unknown one.
"""

from __future__ import annotations

import re
import statistics
import time
import uuid
from dataclasses import dataclass, field

import httpx

from scripts import b3_api as api
from scripts import b3_ops as ops
from scripts.acceptance_common import check, expect, step
from scripts.m4_ops import run_job

PARTY = {"party", "campusfest", "festival", "get-together"}
PARTY_LISTS = {"events-alle", *(f"events-{slug}" for slug in PARTY)}
UID = re.compile(r"^UID:([0-9a-f-]{36})@", re.MULTILINE)
TOKEN_URL = re.compile(r"/ics/p/([A-Za-z0-9_-]{43})\.ics")
NG = "http://localhost:4200"


@dataclass
class Seen:
    """Everything secret the run handled; the log and DB checks search for it."""

    tokens: set[str] = field(default_factory=set)
    addresses: set[str] = field(default_factory=set)

    def address(self, name: str) -> str:
        """Return a fresh address of the run and remember it."""
        address = f"b3-{name}-{uuid.uuid4().hex[:10]}@example.org"
        self.addresses.add(address)
        return address

    def token_of(self, ics_url: str) -> str:
        """Remember and return the token of a profile calendar URL."""
        token = TOKEN_URL.search(ics_url)
        if token is None:
            check(False, "the calendar URL carries a 43-character token")
        assert token is not None
        self.tokens.add(token.group(1))
        return token.group(1)


def event_ids(categories: set[str]) -> set[str]:
    """Return the ids of public events whose category or parent is in `categories`."""
    names = ",".join(f"'{c}'" for c in sorted(categories))
    rows = ops.sql(
        "SELECT id FROM public_event_v "
        f"WHERE category_slug IN ({names}) OR category_parent_slug IN ({names})"
    )
    return {r[0] for r in rows}


def calendar_uids(client: httpx.Client, token: str) -> tuple[httpx.Response, set[str]]:
    """Fetch a profile calendar; return the response and its event ids."""
    response = client.get(f"/ics/p/{token}.ics")
    return response, set(UID.findall(response.text.replace("\r\n ", "")))


def confirm_by_mail(client: httpx.Client, seen: Seen, address: str) -> str:
    """Wait for the DOI mail, confirm it with the POST and return the DOI token."""
    mail = api.wait_mail(address, "bestätige")
    check(mail.kind == "bestaetigen" and mail.token is not None, "the DOI mail links /bestaetigen")
    assert mail.token is not None
    seen.tokens.add(mail.token)
    done = client.post("/api/public/subscriptions/confirm", json={"token": mail.token})
    expect(done, 200, "the POST button confirms")
    return mail.token


def status_of(address_hmac_sql: str) -> str:
    """Return the status of the subscriber selected by a WHERE clause."""
    return ops.value(f"SELECT status FROM subscriber WHERE {address_hmac_sql}")


def check_profile(client: httpx.Client, seen: Seen, party: str, meeting: str) -> str:
    """Item a: calendar profile and mail profile for "only parties, no meetings"."""
    response = api.sign_up(client, interests=["party"], meetings=False)
    out = expect(response, 202, "a: sign-up without mail")
    check("set-cookie" not in response.headers, "a: the sign-up sets no cookie")
    check({c["slug"] for c in out["profile"]["categories"]} == PARTY, "a: party categories only")
    check(out["profile"]["webcalUrl"].startswith("webcal://"), "a: webcal URL")
    token = seen.token_of(out["profile"]["icsUrl"])
    ics, uids = calendar_uids(client, token)
    check(ics.status_code == 200, "a: the profile calendar answers 200")
    check(ics.headers["content-type"].startswith("text/calendar"), "a: text/calendar")
    check(party in uids and meeting not in uids, "a: the party is in, the meeting is not")
    check(uids <= event_ids(PARTY), f"a: all {len(uids)} events are party events")
    check(not uids & event_ids({"sitzung"}), "a: no meeting event in the calendar")
    address = seen.address("party")
    expect(api.sign_up(client, interests=["party"], email=address), 202, "a: sign-up with mail")
    confirm_by_mail(client, seen, address)
    step(run_job("outbox_run"))
    remote = api.Listmonk().subscriber(address)
    check(remote is not None, "a: the subscriber is in Listmonk")
    assert remote is not None
    lists = api.Listmonk().list_names(remote)
    check(set(lists) == PARTY_LISTS, f"a: Listmonk lists {sorted(lists)}")
    check(set(lists.values()) == {"confirmed"}, "a: every list is confirmed")
    check(sorted(remote["attribs"]["kategorien"]) == sorted(PARTY), "a: attribute kategorien")
    check(api.count_mails(address, "Opt-in") == 0, "a: Listmonk sent no opt-in mail of its own")
    return address


def check_get_does_not_confirm(client: httpx.Client, seen: Seen) -> tuple[str, str]:
    """Item b: GET on the confirmation link through API shell and ng serve changes nothing.

    Returns:
        The address and the calendar token of its sign-up.
    """
    address = seen.address("doi")
    out = expect(api.sign_up(client, interests=["kultur"], email=address), 202, "b: sign-up")
    calendar = seen.token_of(out["profile"]["icsUrl"])
    mail = api.wait_mail(address, "bestätige")
    assert mail.token is not None
    seen.tokens.add(mail.token)
    where = f"confirm_token_hash = encode(sha256('{mail.token}'::bytea), 'hex')"
    check(status_of(where) == "pending", "b: pending after the sign-up")
    for base in (api.API, NG):
        page = httpx.get(f"{base}/bestaetigen/{mail.token}", timeout=20)
        check(page.status_code == 200, f"b: GET {base}/bestaetigen/<token> answers 200")
        check(mail.token not in page.text, "b: the page does not echo the token")
    check(status_of(where) == "pending", "b: still pending after the GETs")
    preview = client.post("/api/public/subscriptions/confirm/preview", json={"token": mail.token})
    expect(preview, 200, "b: the preview reads the categories")
    check(status_of(where) == "pending", "b: still pending after the preview")
    confirmed = client.post("/api/public/subscriptions/confirm", json={"token": mail.token})
    expect(confirmed, 200, "b: the POST confirms")
    check(status_of(where) == "", "b: the DOI token hash is gone after the POST")
    again = client.post("/api/public/subscriptions/confirm", json={"token": mail.token})
    expect(again, 404, "b: a second POST is the same 404")
    return address, calendar


def _masked(response: httpx.Response) -> str:
    return TOKEN_URL.sub("/ics/p/<token>.ics", response.text)


def _timed(call) -> tuple[httpx.Response, float]:  # noqa: ANN001
    started = time.monotonic()
    response = call()
    return response, time.monotonic() - started


def check_same_answer(client: httpx.Client, seen: Seen, known: str, rounds: int = 10) -> dict:
    """Item c: same status, body and time for known and unknown addresses, `rounds` each.

    Only the POST is timed; the ALTCHA is solved before the clock starts. The known address has
    used up its three mails of the day by then, so the run also shows that a skipped mail does
    not change the answer.
    """
    samples: dict[str, list[float]] = {
        "known": [],
        "unknown": [],
        "link-known": [],
        "link-unknown": [],
    }
    bodies: dict[str, set[str]] = {k: set() for k in samples}
    codes: dict[str, set[int]] = {k: set() for k in samples}
    for index in range(rounds):
        ops.reset_subscription_limits()
        for kind, address in (("known", known), ("unknown", seen.address(f"u{index}"))):
            payload = api.body(client, interests=["party"], email=address)
            response, took = _timed(
                lambda p=payload: client.post("/api/public/subscriptions", json=p)
            )
            seen.token_of(response.json()["profile"]["icsUrl"])
            samples[kind].append(took)
            bodies[kind].add(_masked(response))
            codes[kind].add(response.status_code)
        for kind, address in (("link-known", known), ("link-unknown", seen.address(f"l{index}"))):
            payload = {"email": address, "altcha": api.altcha(client)}
            response, took = _timed(
                lambda p=payload: client.post("/api/public/subscriptions/manage-link", json=p)
            )
            samples[kind].append(took)
            bodies[kind].add(response.text)
            codes[kind].add(response.status_code)
    ops.reset_subscription_limits()
    medians = {k: round(statistics.median(v) * 1000, 1) for k, v in samples.items()}
    spread = {k: (round(min(v) * 1000, 1), round(max(v) * 1000, 1)) for k, v in samples.items()}
    step(f"c: medians ms {medians}, min/max ms {spread}")
    check(codes["known"] == codes["unknown"] == {202}, "c: sign-up 202 for known and unknown")
    check(bodies["known"] == bodies["unknown"] and len(bodies["known"]) == 1, "c: same body")
    check(codes["link-known"] == codes["link-unknown"] == {202}, "c: manage-link 202 for both")
    check(bodies["link-known"] == bodies["link-unknown"], "c: same manage-link body")
    for a, b in (("known", "unknown"), ("link-known", "link-unknown")):
        check(abs(medians[a] - medians[b]) <= 40, f"c: medians {a}/{b} within 40 ms")
    check(min(min(v) for v in samples.values()) >= 0.6, "c: no answer faster than 0.6 s")
    return {"medians": medians, "spread": spread}


def manage_token(client: httpx.Client, seen: Seen, address: str) -> str:
    """Ask for a management link and return its token from the mail."""
    known = api.count_mails(address, "Verwalten")
    expect(api.manage_link(client, address), 202, "ask for a management link")
    mail = api.wait_mail(address, "Verwalten", known=known)
    check(mail.kind == "abo" and mail.token is not None, "the management mail links /abo")
    assert mail.token is not None
    seen.tokens.add(mail.token)
    return mail.token


def check_rotation(client: httpx.Client, seen: Seen, address: str, old: str) -> None:
    """Item d (B2): rotate the calendar token; the old one is the same 404 as an unknown one."""
    token = manage_token(client, seen, address)
    before, _ = calendar_uids(client, old)
    check(before.status_code == 200, "d: the calendar token works before the rotation")
    headers = {"X-Subscription-Token": token}
    rotated = expect(
        client.post("/api/public/subscriptions/me/ics-token", headers=headers),
        200,
        "d: rotate the calendar token",
    )
    new = seen.token_of(rotated["icsUrl"])
    hashed = ops.value(
        "SELECT count(*) FROM subscription_profile "
        f"WHERE ics_token_hash = encode(sha256('{new}'::bytea), 'hex')"
    )
    check(hashed == "1", "d: the DB holds the SHA-256 of the new token")
    fresh, _ = calendar_uids(client, new)
    check(fresh.status_code == 200, "d: the new token answers 200")
    stale = client.get(f"/ics/p/{old}.ics")
    unknown = client.get(f"/ics/p/{'Z' * 43}.ics")
    check(stale.status_code == unknown.status_code == 404, "d: old and unknown token answer 404")
    same = stale.content == unknown.content and stale.headers.get(
        "content-type"
    ) == unknown.headers.get("content-type")
    check(same, "d: old and unknown token give byte-equal 404 bodies")
