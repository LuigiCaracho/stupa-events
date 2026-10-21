"""The coverage gate script names the critical files below 100 % and spares the exempt ones."""

from __future__ import annotations

from scripts import coverage_critical


def _file(lines: int, branches: int) -> dict:
    return {
        "missing_lines": [1] * lines,
        "summary": {
            "missing_lines": lines,
            "num_branches": 4,
            "covered_branches": 4 - branches,
        },
    }


def test_only_critical_files_below_the_bar_are_reported(monkeypatch) -> None:
    report = {
        "files": {
            "app/modules/auth/router.py": _file(1, 0),
            "app/modules/audit/service.py": _file(0, 2),
            "app/modules/events/lifecycle.py": _file(0, 0),
            "app/modules/files/storage.py": _file(9, 3),
            "app/shared/errors.py": _file(5, 5),
            "worker/scan.py": _file(5, 5),
        }
    }
    assert set(coverage_critical.shortfalls(report)) == {
        "app/modules/auth/router.py",
        "app/modules/audit/service.py",
    }
    monkeypatch.setitem(coverage_critical.EXEMPT, "app/modules/auth/router.py", "reason")
    assert set(coverage_critical.shortfalls(report)) == {"app/modules/audit/service.py"}
