"""Every transition by every user over HTTP, with exact status codes from the oracle.

The rights come from `tests/unit/pipeline/oracle.py` (written from PLAN 4.3, independent of
`TRANSITIONS`). A user who cannot read the dossier gets 404 on the route whose gate is the
session. The dossier is in `fsi`, submitted by `organizer-fsi`, with an image exception and a
date in the future.
"""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api
from tests.unit.pipeline import oracle

pytestmark = pytest.mark.integration

SOURCE_STATE = {
    "T01": "idea",
    "T02": "planning",
    "T03": "in_review",
    "T04": "in_review",
    "T05": "approved",
    "T06": "approved",
    "T07": "live",
    "T08": "live",
    "T08b": "live",
    "T09": "followup",
    "T09b": "followup",
    "T10": "archived",
    "T11": "idea",
    "T12": "withdrawn",
}
ORACLE_ROLE = {
    "viewer-fsi": "viewer",
    "submitter-fsi": "submitter_foreign",
    "organizer-fsi": "organizer",
    "approver-fsi": "organizer",
    "editor": "editor",
    "admin": "admin",
    "stupa": "stupa",
}
INVISIBLE = ("organizer-makers", "approver-stupa", "submitter-ekhg", "member", "nobody")
STATUS = {
    "ok": 200,
    "forbidden": 403,
    "four_eyes": 403,
    "invalid_transition": 409,
    "reason_required": 422,
    "blocked": 422,
}


async def dossier_in(api: Api, state: str) -> str:
    base = {"followup": "live", "archived": "live", "withdrawn": "idea"}.get(state, state)
    event = await api.to_state(base)
    if base != state:
        await api.sql("UPDATE event SET state = :s WHERE id = :i", s=state, i=event["id"])
    return event["id"]


@pytest.mark.parametrize("tid", sorted(SOURCE_STATE))
async def test_every_user_gets_the_status_the_oracle_names(api: Api, tid: str) -> None:
    wrong = []
    for user in [*ORACLE_ROLE, *INVISIBLE]:
        eid = await dossier_in(api, SOURCE_STATE[tid])
        if tid == "T03":
            await api.add_open_comment(eid)
        got = (await api.fire(user, eid, tid, note="Test")).status_code
        if user in INVISIBLE:
            want = 404
        else:
            outcome = oracle.expected(
                tid, SOURCE_STATE[tid], ORACLE_ROLE[user], "exception", "other", "running", True
            )
            want = STATUS[outcome]
        if got != want:
            wrong.append((user, got, want))
    assert not wrong, f"{tid}: {wrong}"
