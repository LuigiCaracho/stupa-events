"""M5 acceptance run against a host-run API and the dev stack (`python -m scripts.m5_acceptance`).

Criterion (PLAN 16.1, row M5; contract 12.3 a to k): the Movienight stock yields a clone
without poster, exception and quotes, its checklist due again and "last time" with visitors
and costs; the 20 sample searches hold; the calendars are golden, readable and carry
cancellations and postponements; the canary finds nothing internal; Schemathesis on the
feed is green; feed snapshots, follow-up, calendar view, archive reading, location and
frame, and the sequence of PLAN 4.6 work end to end. Items l (Playwright) and m
(`restore-smoke.sh`) run outside this script.

Only for the local stack. Every person logs in through the real OIDC flow; SQL reads, moves
clocks (dates, the entry into `followup`) or seeds the synthetic search corpus and the
canary. `--reuse` takes the stock ids of the last run from `/tmp/m5-stock.json`.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from scripts import acceptance_common as common
from scripts import m4_ops as ops
from scripts import m5_fixture as fixture
from scripts.acceptance_common import login, step
from scripts.m5_clone import check_clone
from scripts.m5_followup import check_followup
from scripts.m5_frame import check_archive_reading, check_calendar, check_frame, check_sequence
from scripts.m5_public import check_cache, check_canary, check_ics, check_schemathesis
from scripts.m5_search import check_search

common.PREFIX[0] = "m5"
STOCK_FILE = Path("/tmp/m5-stock.json")


def stock_for(organizer: object, editor: object) -> fixture.Stock:
    """Build the 23 copies, or reuse the ids of the previous run with `--reuse`."""
    if "--reuse" in sys.argv and STOCK_FILE.exists():
        step(f"stock: reusing {STOCK_FILE}")
        return fixture.Stock(**json.loads(STOCK_FILE.read_text()))
    stock = fixture.build(organizer, editor)  # type: ignore[arg-type]
    STOCK_FILE.write_text(json.dumps(asdict(stock)))
    return stock


def main() -> None:
    """Run the M5 acceptance checks in contract order (`--only a,b` limits the items)."""
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), "abcdefghijk")
    ops.reset_upload_limits()
    organizer, editor = login("organizer-fsi"), login("editor")
    makers, member, viewer = login("organizer-makers"), login("member"), login("viewer-fsi")
    stock = stock_for(organizer, editor)
    if "a" in only:
        check_clone(organizer, editor, makers, stock)
    if "b" in only:
        check_search()
    if "c" in only:
        check_ics(organizer, editor)
    if "d" in only:
        check_canary(organizer, editor, member, makers, viewer, stock.archived[-1])
    if "e" in only:
        check_schemathesis()
    if "f" in only:
        check_cache(organizer, editor)
    if "g" in only:
        check_followup(organizer, editor)
    if "h" in only:
        check_calendar(organizer, editor, makers, stock)
    if "i" in only:
        check_archive_reading(organizer, editor, member, makers)
    if "j" in only:
        check_frame(organizer, editor)
    if "k" in only:
        check_sequence(organizer, editor)
    step(f"all checks passed ({date.today().isoformat()})")


if __name__ == "__main__":
    main()
