"""B3 acceptance against host API, worker and local Listmonk: `python -m scripts.b3_acceptance`.

Criterion (PLAN 16.2 B2 token part and B3): "only parties, no meetings" gives a profile, a
calendar and the matching Listmonk lists (a); a GET on the confirmation link confirms nothing (b);
known and unknown addresses get the same answer in the same time (c); a rotated calendar token is
the same 404 as an unknown one (d); Listmonk down loses nothing (e); the digest is a draft (f); an
opt-out in Listmonk stays after the reconcile (g); delete removes address, profile, token and the
Listmonk record (h); tokens only as hashes, no token or address in any log (i).

Only for the local stack: it logs in through the dev Keycloak, publishes one party and one meeting
of the FSI in the current Berlin week, stops and starts the Listmonk container, clears the
subscription rate-limit counters in Redis and runs the Listmonk jobs on the running worker. Needs
`LISTMONK_API_USER`/`LISTMONK_API_TOKEN` in the environment (backend/dev.env.local).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.modules.subscriptions.digest import week_start_of
from scripts import b3_api as api
from scripts import b3_ops as ops
from scripts.acceptance_common import PREFIX, login, step
from scripts.b3_flow import (
    Seen,
    check_get_does_not_confirm,
    check_profile,
    check_rotation,
    check_same_answer,
)
from scripts.b3_listmonk import check_digest, check_erase, check_outage, check_unsubscribe
from scripts.b3_secrets import check_secrets
from scripts.m5_live import live

PREFIX[0] = "b3"


def this_week_slot(now: datetime) -> tuple[datetime, datetime]:
    """Return a two-hour slot that starts in an hour or later and ends inside the Berlin week."""
    berlin = ZoneInfo("Europe/Berlin")
    week_end = datetime.combine(
        week_start_of(now) + timedelta(days=7), datetime.min.time(), tzinfo=berlin
    )
    start = min(now + timedelta(hours=20), week_end - timedelta(hours=3)).replace(
        minute=0, second=0, microsecond=0
    )
    return start, start + timedelta(hours=2)


def main() -> None:
    """Run the B3 acceptance."""
    started = datetime.now(UTC)
    since = started.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    ops.reset_subscription_limits()
    organizer, editor = login("organizer-fsi"), login("editor")
    slot = this_week_slot(started)
    party = live(organizer, "B3 Semesterparty", times=slot, category="party")
    meeting = live(organizer, "B3 StuPa-Sitzung", times=slot, category="sitzung")
    step(f"published party {party} and meeting {meeting} at {slot[0].isoformat()}")
    seen = Seen()
    with api.anonymous() as client:
        party_address = check_profile(client, seen, party, meeting)
        doi_address, calendar = check_get_does_not_confirm(client, seen)
        check_rotation(client, seen, doi_address, calendar)
        timing = check_same_answer(client, seen, doi_address)
        outage_address = check_outage(client, seen)
        check_digest(editor, party_address)
        check_unsubscribe(party_address)
        check_erase(client, seen, outage_address)
    sizes = check_secrets(seen, since)
    step(f"summary {json.dumps({'timing': timing, 'logLines': sizes})}")
    step("all checks passed")


if __name__ == "__main__":
    main()
