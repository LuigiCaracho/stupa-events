"""Load the synthetic search corpus (`tests/fixtures/search/corpus.yaml`) through plain SQL."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text

from tests.integration.events.harness import Api

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "search"
INSERT_EVENT = text(
    "INSERT INTO event (title, state, starts_at, ends_at, organization_id, format_id, created_by,"
    " summary) VALUES (:title, :state, CAST(:start AS timestamptz),"
    " CAST(:start AS timestamptz) + interval '3 hours', (SELECT id FROM organization WHERE slug = :org),"
    " (SELECT id FROM format WHERE slug = :format), 'seed', :summary) RETURNING id"
)
INSERT_DOCUMENT = text(
    "INSERT INTO document (event_id, kind, title, body_md, visibility)"
    " VALUES (:event, :kind, :title, :body, :visibility)"
)


def load_yaml(name: str) -> Any:
    """Read one fixture file of the search tests."""
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


async def load_corpus(api: Api) -> dict[str, str]:
    """Insert dossiers and documents; return `{title: id}`."""
    corpus = load_yaml("corpus.yaml")
    ids: dict[str, str] = {}
    async with api.maker() as session:
        for item in corpus["events"]:
            event_id = (
                await session.execute(
                    INSERT_EVENT,
                    {
                        "title": item["title"],
                        "state": item["state"],
                        "start": datetime.fromisoformat(item["start"]),
                        "org": item["org"],
                        "format": item.get("format"),
                        "summary": item.get("summary"),
                    },
                )
            ).scalar_one()
            ids[item["title"]] = str(event_id)
            for doc in item.get("documents", []):
                await session.execute(
                    INSERT_DOCUMENT,
                    {
                        "event": event_id,
                        "kind": doc["kind"],
                        "title": doc["title"],
                        "body": doc["body"],
                        "visibility": doc["visibility"],
                    },
                )
        await session.commit()
    return ids
