"""Gate for the critical packages: 100 % line and branch coverage (PLAN 12.1).

Run after `pytest --cov` (it reads `.coverage`):

    uv run python -m scripts.coverage_critical

The packages are `auth`, `audit` and `publicapi` (with `ics/`); the single files of
`CRITICAL_FILES` (uploads, sniffing, comments, checklist, notification fan-out, the packages
`archive` and `search`, `formats/service.py`, `worker/public_cache.py`; since M5b the
lifecycle of the dossier: `events/lifecycle.py`, `publish.py`, `hints.py`, `allowed.py`,
`editing.py`, `step.py`, `public_status.py` and `worker/advance.py`). A file may
sit in `EXEMPT` with the reason why it stays below 100 % until a later milestone changes it.
Exit status 1 lists the files below the bar.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import coverage

CRITICAL = ("auth", "audit", "publicapi", "archive", "search")
CRITICAL_FILES = frozenset(
    {
        "app/modules/files/attachments.py",
        "app/modules/files/mime.py",
        "app/modules/dossier/comments.py",
        "app/modules/dossier/checklist.py",
        "app/modules/notifications/service.py",
        "app/modules/formats/service.py",
        "worker/public_cache.py",
        "app/modules/events/lifecycle.py",
        "app/modules/events/publish.py",
        "app/modules/events/hints.py",
        "app/modules/events/allowed.py",
        "app/modules/events/editing.py",
        "app/modules/events/step.py",
        "app/modules/events/public_status.py",
        "worker/advance.py",
    }
)
EXEMPT: dict[str, str] = {}


def shortfalls(report: dict) -> dict[str, str]:
    """Return `{file: what is missing}` of each critical file below 100 %, exempt ones left out."""
    found: dict[str, str] = {}
    for name, data in sorted(report["files"].items()):
        parts = Path(name).parts
        in_package = len(parts) >= 3 and parts[:2] == ("app", "modules") and parts[2] in CRITICAL
        if not in_package and name not in CRITICAL_FILES:
            continue
        summary = data["summary"]
        lines, branches = (
            summary["missing_lines"],
            summary["num_branches"] - summary["covered_branches"],
        )
        if (lines or branches) and name not in EXEMPT:
            found[name] = f"{lines} line(s), {branches} branch(es) missing: {data['missing_lines']}"
    return found


def main() -> int:
    """Check the data of the last run and print the files below the bar."""
    cov = coverage.Coverage()
    cov.load()
    with tempfile.NamedTemporaryFile(suffix=".json") as out:
        cov.json_report(outfile=out.name, ignore_errors=True)
        report = json.loads(Path(out.name).read_text(encoding="utf-8"))
    missing = shortfalls(report)
    for name, what in missing.items():
        print(f"coverage_critical: {name}: {what}", file=sys.stderr)
    print(
        f"coverage_critical: {'FAILED' if missing else 'ok'} ({len(missing)} file(s) below 100 %)"
    )
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
