"""Item g of the M5 acceptance: follow-up with a set clock, T09 with real guards, T09b, T10.

Three live Movienight dossiers. The clock moves by SQL only (`ends_at`, and the `at` of
the entry into `followup` with its append-only trigger off for that one update); the states
move through the worker (`advance_states`) and the API. The reminder job runs once to clear
the dev backlog, then once for the dossier a week in `followup` and once more, which must
send nothing.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from uuid import UUID

import httpx

from app.modules.notifications.mail import compute_idempotency_key
from scripts import m3_worker as clock
from scripts import m4_acceptance as m4
from scripts import m4_ops as ops
from scripts.acceptance_common import check, expect, step
from scripts.m5_live import live

PG = "stupa-events-dev-postgres-1"
ORDER = ["retrospective_missing", "outcome_missing", "howto_unverified"]


def _movienight(organizer: httpx.Client, editor: httpx.Client, title: str) -> str:
    eid = live(organizer, editor, title, days=39, fmt="movienight")
    check(
        organizer.get(f"/api/events/{eid}").json()["format"]["slug"] == "movienight",
        f"g: {title} is a Movienight",
    )
    return eid


def _state(client: httpx.Client, eid: str) -> dict:
    return expect(client.get(f"/api/events/{eid}"), 200, "g: read the dossier")


def _enter_followup_days_ago(eid: str, days: int) -> None:
    """Move the entry into `followup` back by `days` (one superuser transaction).

    `event_status_event` is append-only (trigger), and a job run with a moved `now` would
    move every dev dossier; so the trigger is off for this one update only.
    """
    UUID(eid)
    sql = (
        "BEGIN; ALTER TABLE event_status_event DISABLE TRIGGER trg_event_status_event_no_update;"
        f" UPDATE event_status_event SET at = now() - interval '{int(days)} days'"
        f" WHERE event_id = '{eid}' AND to_state = 'followup';"
        " ALTER TABLE event_status_event ENABLE TRIGGER trg_event_status_event_no_update; COMMIT;"
    )
    subprocess.run(
        [
            "docker",
            "exec",
            PG,
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "events",
            "-c",
            sql,
        ],
        check=True,
        capture_output=True,
    )


def _format_verified() -> tuple[datetime | None, datetime | None]:
    row = ops.query(
        "SELECT f.last_verified_at, d.verified_at FROM format f"
        " LEFT JOIN document d ON d.id = f.master_howto_document_id WHERE f.slug = 'movienight'"
    )
    return row[0][0], row[0][1]


def _reminders(eid: str) -> list[str]:
    rows = ops.query(
        "SELECT id::text FROM notification WHERE event_id = :e AND kind = 'followup_reminder'",
        e=eid,
    )
    return [r[0] for r in rows]


def check_reminder(eid: str) -> None:
    """Exactly one reminder a week after the entry, a second run sends nothing."""
    step(f"g: warm-up {ops.run_job('send_followup_reminders')}")
    check(not _reminders(eid), "g: no reminder before seven days")
    _enter_followup_days_ago(eid, 8)
    first = ops.run_job("send_followup_reminders")
    second = ops.run_job("send_followup_reminders")
    step(f"g: {first} / {second}")
    check("mails=0" in second, "g: the second run sends nothing")
    rows = _reminders(eid)
    check(len(rows) >= 1, f"g: {len(rows)} followup_reminder row(s), one per owner")
    job = compute_idempotency_key("notif", rows[0])
    check(ops.job_result(job) == "sent", "g: the reminder mail was sent by the worker")


def check_t09(organizer: httpx.Client, eid: str) -> None:
    """T09 refused with the reasons, then accepted; the format and its master howto dated."""
    refused = organizer.post(
        f"/api/events/{eid}/transitions/T09", json={}, headers=m4.etag(organizer, eid)
    )
    codes = m4.reasons(refused)
    check(refused.status_code == 422 and all(c in codes for c in ORDER), f"g: T09 -> 422 {codes}")
    expect(
        organizer.post(
            f"/api/events/{eid}/documents", json={"kind": "retrospective", "bodyMd": "Gut besucht."}
        ),
        201,
        "g: retrospective",
    )
    expect(
        organizer.put(
            f"/api/events/{eid}/outcome",
            json={"attendance": 55, "costsCents": 9000},
            headers=m4.etag(organizer, eid),
        ),
        200,
        "g: outcome",
    )
    expect(organizer.post(f"/api/events/{eid}/actions/verify-howto"), 200, "g: verify howto")
    before = datetime.now().astimezone()
    m4.fire(organizer, eid, "T09")
    verified, master = _format_verified()
    check(
        verified is not None and verified >= before - timedelta(seconds=5),
        f"g: format.last_verified_at {verified}",
    )
    check(
        master is not None and master >= before - timedelta(seconds=5),
        f"g: master howto verified {master}",
    )


def check_t09b(organizer: httpx.Client, editor: httpx.Client, eid: str, organizer_sub: str) -> None:
    """T09b after 30 days: the mark, the mail, the format untouched; verify, then T10."""
    untouched = _format_verified()[0]
    _enter_followup_days_ago(eid, 31)
    line = clock.run_advance_once()
    check("archived=" in line and "archived=0" not in line, "g: the worker archives through T09b")
    event = _state(organizer, eid)
    check(
        event["state"] == "archived" and event["howtoUnverified"] is True,
        "g: archived, 'Anleitung ungeprüft'",
    )
    check(_format_verified()[0] == untouched, "g: T09b leaves the format untouched")
    row = ops.query(
        "SELECT id::text FROM notification WHERE event_id = :e AND kind = 'auto_archived'"
        " AND recipient_sub = :s",
        e=eid,
        s=organizer_sub,
    )
    check(len(row) == 1, "g: one auto_archived row for the organizer")
    check(
        ops.job_result(compute_idempotency_key("notif", row[0][0])) == "sent",
        "g: mail auto_archived sent",
    )
    fixed = expect(
        organizer.post(f"/api/events/{eid}/actions/verify-howto"),
        200,
        "g: verify-howto in archived",
    )
    check(fixed["howtoUnverified"] is False, "g: the mark is gone")
    check(_format_verified()[0] != untouched, "g: verify-howto in archived dates the format")
    reopened = m4.fire(editor, eid, "T10", note="Nachtrag zur Abrechnung")
    check(reopened["state"] == "followup", "g: T10 opens the follow-up again")


def check_followup(organizer: httpx.Client, editor: httpx.Client) -> None:
    """Run item g."""
    organizer_sub = organizer.get("/api/auth/me").json()["sub"]
    first = _movienight(organizer, editor, "M5 Nachbereitung")
    second = _movienight(organizer, editor, "M5 Ohne Nachbereitung")
    early = _movienight(organizer, editor, "M5 Noch nicht vorbei")
    for eid in (first, second):
        clock.shift_dates(eid, **clock.ended(13))
    clock.shift_dates(early, **clock.ended(11))
    clock.run_advance_once()
    check(_state(organizer, first)["state"] == "followup", "g: T08 twelve hours after the end")
    check(
        _state(organizer, early)["state"] == "live", "g: eleven hours after the end it stays live"
    )
    check_reminder(first)
    check_t09(organizer, first)
    check_t09b(organizer, editor, second, organizer_sub)
