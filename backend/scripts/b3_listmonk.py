"""B3 acceptance against the local Listmonk: outage, digest draft, opt-out, erasure.

Item e: with the Listmonk container stopped a sign-up and its confirmation still work, the
outbox grows and nothing is lost; after the start the outbox drains and the person is in
Listmonk. Item f: the digest job leaves campaign drafts, nothing is sent until the release.
Item g: an unsubscribe on the Listmonk page ("from all future mails") becomes `unsubscribed`
in the reconcile and stays so after a second reconcile. Item h: "delete everything" removes
address, profile, tokens and the Listmonk record.
"""

from __future__ import annotations

import re
import time

import httpx

from app.modules.subscriptions.digest import week_start_of
from app.shared.timeutil import utcnow
from scripts import b3_api as api
from scripts import b3_ops as ops
from scripts.acceptance_common import check, expect, step
from scripts.b3_flow import Seen, confirm_by_mail, manage_token
from scripts.m4_ops import run_job

DIGEST_SUBJECT = "STUPA Events: Das ist diese Woche los"
UNSUB = re.compile(r"<(http://127\.0\.0\.1:9002/subscription/[0-9a-f-]+/[0-9a-f-]+)>")


def pending_jobs() -> int:
    """Count the outbox jobs that still wait."""
    return int(ops.value("SELECT count(*) FROM outbox WHERE state IN ('pending', 'running')"))


def subscriber_where(address_token: str) -> str:
    """Return a WHERE clause for the subscriber whose management token hash matches."""
    return f"manage_token_hash = encode(sha256('{address_token}'::bytea), 'hex')"


def wait_listmonk(up: bool, timeout: float = 90) -> None:
    """Wait until Listmonk answers (or stops answering)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if api.Listmonk().healthy() == up:
            return
        time.sleep(2)
    check(False, f"Listmonk {'up' if up else 'down'} within {timeout:.0f} s")


def drain_outbox(timeout: float = 240) -> int:
    """Run the outbox job until nothing waits; return the number of runs."""
    deadline, runs = time.monotonic() + timeout, 0
    while time.monotonic() < deadline:
        runs += 1
        step(run_job("outbox_run"))
        if pending_jobs() == 0:
            return runs
        time.sleep(10)
    check(False, "the outbox drained")
    return runs


def check_outage(client: httpx.Client, seen: Seen) -> str:
    """Item e: Listmonk down loses nothing."""
    drain_outbox()
    before = pending_jobs()
    ops.listmonk_stop()
    wait_listmonk(False)
    step("e: Listmonk container stopped")
    try:
        address = seen.address("outage")
        expect(api.sign_up(client, interests=["sport"], email=address), 202, "e: sign-up")
        confirm_by_mail(client, seen, address)
        check(pending_jobs() == before + 1, f"e: the outbox grew to {before + 1}")
        step(run_job("outbox_run"))
        failed = ops.sql("SELECT state, attempts, last_error FROM outbox WHERE attempts > 0")
        check(any(r[0] == "pending" for r in failed), f"e: the failed job waits again {failed}")
        check(pending_jobs() == before + 1, "e: nothing was lost while Listmonk was down")
    finally:
        ops.listmonk_start()
    wait_listmonk(True)
    step("e: Listmonk container started")
    runs = drain_outbox()
    check(pending_jobs() == 0, f"e: the outbox is empty after {runs} runs")
    check(api.Listmonk().subscriber(address) is not None, "e: the subscriber reached Listmonk")
    dead = ops.value("SELECT count(*) FROM outbox WHERE state = 'dead'")
    check(dead == "0", "e: no job is dead")
    return address


def reset_digest_week(week: str) -> None:
    """Forget this week's digest runs and their campaigns, so a second run starts clean."""
    listmonk = api.Listmonk()
    for campaign in listmonk.campaigns(f"events-digest-{week}"):
        listmonk.http.delete(f"/api/campaigns/{int(campaign['id'])}")
    ops.sql(f"DELETE FROM digest_run WHERE week_start = '{week}'")


def check_digest(editor: httpx.Client, party_address: str) -> None:
    """Item f: the digest job leaves drafts; the release sends the party list only."""
    week = week_start_of(utcnow()).isoformat()
    reset_digest_week(week)
    step(run_job("reconcile_listmonk"))
    step(run_job("build_digest_drafts"))
    runs = ops.sql(
        f"SELECT list_key, status, campaign_id FROM digest_run WHERE week_start = '{week}'"
    )
    keys = {r[0]: r for r in runs}
    check("party" in keys and "_all" in keys, f"f: digest runs for party and _all ({sorted(keys)})")
    check(keys["party"][1] == keys["_all"][1] == "draft", "f: party and _all are drafts")
    skipped = sorted(k for k, r in keys.items() if r[1] == "skipped")
    check(
        {r[1] for r in runs} <= {"draft", "skipped"} and "sitzung" in skipped,
        f"f: lists without subscribers are skipped ({skipped}), nothing else",
    )
    listmonk = api.Listmonk()
    drafts = {c["name"]: c["status"] for c in listmonk.campaigns(f"events-digest-{week}")}
    check(drafts.get(f"events-digest-{week}-party") == "draft", "f: the party campaign is a draft")
    check(set(drafts.values()) == {"draft"}, f"f: all {len(drafts)} campaigns are drafts")
    check(api.count_mails(party_address, DIGEST_SUBJECT) == 0, "f: no digest mail went out")
    step(run_job("build_digest_drafts"))
    again = ops.value(f"SELECT count(*) FROM digest_run WHERE week_start = '{week}'")
    check(int(again) == len(runs), "f: a second run creates nothing new")
    listed = expect(editor.get("/api/admin/digests"), 200, "f: the editor lists the drafts")
    party = next(r for r in listed if r["listKey"] == "party" and r["weekStart"] == week)
    expect(editor.post(f"/api/admin/digests/{party['id']}/release"), 204, "f: release party")
    status = listmonk.campaigns(f"events-digest-{week}-party")[0]["status"]
    check(status in {"running", "finished"}, f"f: the released campaign runs ({status})")
    api.wait_mail(party_address, DIGEST_SUBJECT, timeout=120)
    others = [r for r in listed if r["listKey"] != "party" and r["weekStart"] == week]
    check(all(r["status"] != "released" for r in others), "f: the other drafts stay unsent")
    step("f: the released digest reached the party subscriber")


def check_unsubscribe(party_address: str) -> None:
    """Item g: an opt-out in Listmonk wins and stays after a second reconcile."""
    mail = api.wait_mail(party_address, DIGEST_SUBJECT)
    headers = api.mail_headers(mail.id)
    check(headers.get("List-Unsubscribe-Post") == ["List-Unsubscribe=One-Click"], "g: one-click")
    link = UNSUB.search(headers["List-Unsubscribe"][0])
    check(link is not None, "g: List-Unsubscribe points at the Listmonk page")
    assert link is not None
    page = httpx.post(link.group(1), data={"blocklist": "true"}, timeout=15)
    check(page.status_code == 200, "g: the person unsubscribes from all mails on the page")
    remote = api.Listmonk().subscriber(party_address)
    check(remote is not None and remote["status"] == "blocklisted", "g: Listmonk blocklisted")
    where = "status IN ('confirmed', 'unsubscribed') AND listmonk_subscriber_id = " + str(
        remote["id"] if remote else 0
    )
    check(ops.value(f"SELECT status FROM subscriber WHERE {where}") == "confirmed", "g: before")
    step(run_job("reconcile_listmonk"))
    check(ops.value(f"SELECT status FROM subscriber WHERE {where}") == "unsubscribed", "g: taken")
    mail_on = ops.value(
        "SELECT p.mail_enabled FROM subscription_profile p JOIN subscriber s "
        f"ON s.id = p.subscriber_id WHERE {where.replace('status', 's.status')}"
    )
    check(mail_on == "f", "g: the profile mail is off")
    step(run_job("outbox_run"))
    step(run_job("reconcile_listmonk"))
    check(ops.value(f"SELECT status FROM subscriber WHERE {where}") == "unsubscribed", "g: stays")
    again = api.Listmonk().subscriber(party_address)
    check(again is not None and again["status"] == "blocklisted", "g: Listmonk stays blocklisted")


def check_erase(client: httpx.Client, seen: Seen, address: str) -> None:
    """Item h: delete everything removes address, profile, tokens and the Listmonk record."""
    token = manage_token(client, seen, address)
    me = expect(api.me(client, token), 200, "h: the management page loads")
    check(me["mailEnabled"] is True and me["icsUrl"] is None, "h: me shows no calendar URL")
    sid = ops.value(f"SELECT id FROM subscriber WHERE {subscriber_where(token)}")
    check(bool(sid), "h: the subscriber exists")
    remote = api.Listmonk().subscriber(address)
    check(remote is not None, "h: Listmonk holds the subscriber before")
    gone = api.me(client, token, "DELETE")
    check(gone.status_code == 204, "h: DELETE me answers 204")
    row = ops.sql(
        "SELECT status, email_enc IS NULL, email_hmac IS NULL, manage_token_hash IS NULL, "
        "confirm_token_hash IS NULL, listmonk_subscriber_id IS NULL FROM subscriber "
        f"WHERE id = '{sid}'"
    )[0]
    check(row == ["erased", "t", "t", "t", "t", "t"], f"h: tombstone without personal data {row}")
    profiles = ops.value(f"SELECT count(*) FROM subscription_profile WHERE subscriber_id = '{sid}'")
    check(profiles == "0", "h: the profile with its calendar token is gone")
    expect(api.me(client, token), 404, "h: the management token is dead")
    drain_outbox()
    job = ops.sql(
        "SELECT state, payload ? 'emailEnc' FROM outbox "
        f"WHERE op = 'delete' AND subscriber_id = '{sid}'"
    )
    check(
        bool(job) and job[0] == ["done", "f"], f"h: the delete job is done without ciphertext {job}"
    )
    check(api.Listmonk().subscriber(address) is None, "h: Listmonk has no record any more")
