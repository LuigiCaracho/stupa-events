"""Gate for the critical packages: 100 % line and branch coverage (PLAN 12.1).

Run after `pytest --cov` (it reads `.coverage`):

    uv run python -m scripts.coverage_critical

The packages are `auth`, `audit`, `pipeline` and `publicapi`. A file may sit in `EXEMPT`
with the reason why it stays below 100 % until a later milestone changes it. `files` and
`media` follow with M4, which changes them (M2 contract, 10.2). Exit status 1 lists the
files below the bar.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import coverage

CRITICAL = ("auth", "audit", "pipeline", "publicapi")
EXEMPT: dict[str, str] = {}


def shortfalls(report: dict) -> dict[str, str]:
    """Return `{file: what is missing}` of each critical file below 100 %, exempt ones left out."""
    found: dict[str, str] = {}
    for name, data in sorted(report["files"].items()):
        parts = Path(name).parts
        if len(parts) < 3 or parts[:2] != ("app", "modules") or parts[2] not in CRITICAL:
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
