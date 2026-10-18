"""Seed a development database: reference rows and a few dossiers (`python -m scripts.seed_dev`).

The dossiers come from `seeds/dev_events.yaml` and go through the real services as a
seed editor, so revisions, status events and audit entries exist like in production. A
dossier is skipped when its title already exists in the organization, so the script can
run twice. It never touches a live system: it uses `DATABASE_URL` of the environment.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker
from app.modules.auth.principal import Principal
from app.modules.events.models import Event
from app.modules.events.schemas import EventCreate
from app.modules.events.service import EventService
from app.modules.orgs.models import Organization
from app.modules.pipeline.service import PipelineService
from app.modules.taxonomy.models import Category
from app.modules.taxonomy.seeding import ensure_reference
from app.shared.permissions import permissions_of
from app.shared.timeutil import utcnow

SEEDS = Path(__file__).resolve().parents[1] / "seeds" / "dev_events.yaml"


def seed_editor() -> Principal:
    """Return the principal that creates the dev dossiers (global editor role)."""
    roles = ["member", "editor"]
    return Principal(sub="seed-dev", roles=roles, permissions=set(permissions_of(roles)))


def load_definitions(path: Path = SEEDS) -> list[dict[str, Any]]:
    """Read the dossier definitions of the YAML file."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))["events"]


async def _ids(session: AsyncSession, model: type[Organization] | type[Category]) -> dict[str, Any]:
    return {slug: id_ for slug, id_ in await session.execute(select(model.slug, model.id))}


async def seed_event(
    session: AsyncSession, principal: Principal, definition: dict[str, Any], ids: dict[str, dict]
) -> bool:
    """Create one dossier and move it to its stage. Return `False` when it exists."""
    organization_id = ids["organization"][definition["organization"]]
    exists = await session.scalar(
        select(Event.id).where(
            Event.organization_id == organization_id, Event.title == definition["title"]
        )
    )
    if exists is not None:
        return False
    start = (utcnow() + timedelta(days=definition["startsInDays"])).replace(
        minute=0, second=0, microsecond=0
    )
    created = await EventService(session).create(
        principal,
        EventCreate.model_validate(
            {
                "title": definition["title"],
                "startsAt": start,
                "endsAt": start + timedelta(hours=definition["durationHours"]),
                "organizationId": organization_id,
                "venueText": definition.get("venueText"),
                "primaryCategoryId": ids["category"][definition["category"]],
                "summary": definition.get("summary"),
            }
        ),
    )
    if definition.get("stage") == "planning":
        await PipelineService(session).stage_fire(principal, created.id, "T01")
    return True


async def main() -> int:
    """Seed the database of `DATABASE_URL` and return the number of new dossiers."""
    async with get_sessionmaker()() as session:
        await ensure_reference(session)
        ids = {
            "organization": await _ids(session, Organization),
            "category": await _ids(session, Category),
        }
        principal = seed_editor()
        results = [await seed_event(session, principal, d, ids) for d in load_definitions()]
        await session.commit()
    return sum(results)


if __name__ == "__main__":
    print(f"seeded {asyncio.run(main())} new dossier(s)")
