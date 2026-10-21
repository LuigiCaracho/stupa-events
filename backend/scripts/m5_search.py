"""Item b of the M5 acceptance: the 20 sample searches of `queries.yaml` on the dev stack.

The synthetic corpus (`tests/fixtures/search/corpus.yaml`) goes into the dev database once,
by SQL as in the integration test, marked `created_by = 'm5-corpus'`. The dev database holds
far more dossiers than the corpus, so each case walks every page of the answer and compares
the corpus hits with the expected set; hits outside the corpus are counted, not judged.
`first` is checked among the corpus hits.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from scripts import m4_ops as ops
from scripts.acceptance_common import check, expect, login, step

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "search"
MARK = "m5-corpus"
PAGE = 50
EXCEPTION = (
    '{"granted_by": "seed", "reason": "Testdaten ohne Motiv", "at": "2026-01-01T00:00:00+00:00"}'
)
INSERT_EVENT = (
    "INSERT INTO event (title, state, starts_at, ends_at, organization_id, format_id, created_by,"
    " image_exception) VALUES (:title, :state, CAST(:start AS timestamptz),"
    " CAST(:start AS timestamptz) + interval '3 hours',"
    " (SELECT id FROM organization WHERE slug = :org),"
    " (SELECT id FROM format WHERE slug = :format), :mark,"
    " CAST(:exception AS jsonb)) RETURNING id"
)
INSERT_DOCUMENT = (
    "INSERT INTO document (event_id, kind, title, body_md, visibility)"
    " VALUES (:event, :kind, :title, :body, :visibility)"
)


def _yaml(name: str) -> Any:
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


def load_corpus() -> dict[str, str]:
    """Insert the corpus unless it is there; return `{id: title}` of its dossiers and documents."""
    if not ops.query("SELECT 1 FROM event WHERE created_by = :m LIMIT 1", m=MARK):
        for item in _yaml("corpus.yaml")["events"]:
            event_id = ops.query(
                INSERT_EVENT,
                title=item["title"],
                state=item["state"],
                start=datetime.fromisoformat(item["start"]),
                org=item["org"],
                format=item.get("format"),
                mark=MARK,
                exception=EXCEPTION,
            )[0][0]
            for doc in item.get("documents", []):
                ops.query(INSERT_DOCUMENT, event=event_id, **_document(doc))
        step("b: corpus inserted")
    events = ops.query("SELECT id::text, title FROM event WHERE created_by = :m", m=MARK)
    docs = ops.query(
        "SELECT d.id::text, d.title FROM document d JOIN event e ON e.id = d.event_id"
        " WHERE e.created_by = :m",
        m=MARK,
    )
    return dict(events + docs)


def _document(doc: dict[str, str]) -> dict[str, str]:
    return {k: doc[k] for k in ("kind", "title", "visibility")} | {"body": doc["body"]}


def walk(client: httpx.Client, q: str, params: dict[str, Any]) -> tuple[int, list[dict]]:
    """Return the total and every hit of a search, page by page."""
    hits: list[dict] = []
    total = 0
    while True:
        page = expect(
            client.get(
                "/api/search", params={"q": q, "limit": PAGE, "offset": len(hits), **params}
            ),
            200,
            f"b: search '{q}' offset {len(hits)}",
        )
        total = page["total"]
        hits += page["hits"]
        if not page["hits"] or len(hits) >= total:
            return total, hits


def check_search() -> None:
    """Run the 20 cases as the persons named in `queries.yaml`."""
    corpus = load_corpus()
    clients: dict[str, httpx.Client] = {}
    for case in _yaml("queries.yaml"):
        client = clients.get(case["as"]) or clients.setdefault(case["as"], login(case["as"]))
        params = {"scope": case.get("scope", "events"), **case.get("params", {})}
        total, hits = walk(client, case["q"], params)
        check(total == len(hits), f"b{case['n']:02d}: total {total} equals the walked hits")
        ours = [h["title"] for h in hits if str(h["id"]) in corpus]
        line = f"b{case['n']:02d}: '{case['q']}' as {case['as']} -> corpus {len(ours)}"
        check(
            sorted(ours) == sorted(case["expect"]),
            f"{line}, outside {total - len(ours)}: {sorted(ours)}",
        )
        if "first" in case:
            check(ours[0] == case["first"], f"b{case['n']:02d}: '{case['first']}' ranks first")
    for client in clients.values():
        client.close()
