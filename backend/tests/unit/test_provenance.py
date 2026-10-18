"""Every file with a provenance line is listed in the manifests, and the other way round.

The manifests are `PROVENANCE.json` and the per-builder parts `PROVENANCE.<builder>.json`
in the repo root. A listed file must exist, carry the line for its source, and have the
mode `K` (copied) or `U` (copied and changed).

While the builders still work in parallel, only `backend/` and the top-level directories
that a manifest already mentions are scanned. With `PROVENANCE_STRICT=1` (CI, after the
manifests are merged) the whole repo is scanned.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MARKER = "Copied from " + "STUPA-Workflow@"
_LINE = re.compile(re.escape(MARKER) + r"(?P<commit>[0-9a-f]+) (?P<source>\S+)")
_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "vendor",
    "dist",
    ".angular",
    "__pycache__",
    "coverage",
    "test-results",
    "playwright-report",
}
_SELF = Path(__file__).resolve()


def _manifest_files() -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for manifest in sorted(ROOT.glob("PROVENANCE*.json")):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["upstream"] == {"repo": "STUPA-MAKERS/STUPA-Workflow", "commit": "93c33d6"}
        files.extend(data["files"])
    return files


def _scanned_areas() -> set[str]:
    if os.environ.get("PROVENANCE_STRICT") == "1":
        return {p.name for p in ROOT.iterdir()}
    return {"backend"} | {f["path"].split("/")[0] for f in _manifest_files()}


@lru_cache
def _stamped_files() -> dict[str, re.Match[str]]:
    found: dict[str, re.Match[str]] = {}
    areas = _scanned_areas()
    for path in ROOT.rglob("*"):
        parts = path.relative_to(ROOT).parts
        if not path.is_file() or path == _SELF or _SKIP_DIRS & set(parts) or parts[0] not in areas:
            continue
        if path.suffix in {".png", ".jpg", ".woff2", ".ico", ".lock", ".json"}:
            continue
        try:
            head = path.read_text(encoding="utf-8")[:4000]
        except (UnicodeDecodeError, OSError):
            continue
        match = _LINE.search(head)
        if match:
            found[path.relative_to(ROOT).as_posix()] = match
    return found


def test_manifest_exists() -> None:
    assert _manifest_files(), "no PROVENANCE*.json with entries in the repo root"


def test_every_stamped_file_is_listed() -> None:
    listed = {f["path"] for f in _manifest_files()}
    missing = sorted(set(_stamped_files()) - listed)
    assert not missing, f"stamped but not in a manifest: {missing}"


def test_every_listed_file_is_stamped() -> None:
    stamped = _stamped_files()
    missing = sorted(f["path"] for f in _manifest_files() if f["path"] not in stamped)
    assert not missing, f"in a manifest but without a provenance line: {missing}"


@pytest.mark.parametrize("entry", _manifest_files(), ids=lambda e: e["path"])
def test_entry_is_consistent(entry: dict[str, str]) -> None:
    assert entry["mode"] in {"K", "U"}
    stamped = _stamped_files().get(entry["path"])
    assert stamped is not None
    assert stamped["commit"] == "93c33d6"
    assert stamped["source"].rstrip(".,;") == entry["source"]
