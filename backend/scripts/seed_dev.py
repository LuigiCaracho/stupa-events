"""Seed a development database: reference rows, mappings, dossiers (`python -m scripts.seed_dev`).

The reference rows (organizations, categories, 44 venues) come from the reference modules.
The group mappings are the proposal of `MappingService.create_defaults` plus the extra rows
of `seeds/dev_mappings.yaml`, so every group of the Keycloak realm means something. The
dossiers come from `seeds/dev_events.yaml` and go through the real services as a seed
editor, so revisions, status events and audit entries exist like in production. Every step
skips what exists, so the script can run twice. It never touches a live system: it uses
`DATABASE_URL` of the environment.
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
from app.modules.admin.mappings_service import MappingService
from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.principal import Principal
from app.modules.events.models import Event
from app.modules.events.schemas import EventCreate
from app.modules.events.service import EventService
from app.modules.orgs.models import GroupMapping, Organization
from app.modules.pipeline.exception import grant_image_exception
from app.modules.pipeline.service import PipelineService
from app.modules.taxonomy.models import Category
from app.modules.taxonomy.seeding import ensure_reference
from app.settings import get_settings
from app.shared.permissions import permissions_of
from app.shared.timeutil import utcnow
from scripts import seed_followup

SEED_DIR = Path(__file__).resolve().parents[1] / "seeds"
SEEDS = SEED_DIR / "dev_events.yaml"
MAPPING_SEEDS = SEED_DIR / "dev_mappings.yaml"


def seed_editor() -> Principal:
    """Return the principal that creates the dev dossiers (global editor role)."""
    roles = ["member", "editor"]
    return Principal(sub="seed-dev", roles=roles, permissions=set(permissions_of(roles)))


async def seed_member(session: AsyncSession) -> Principal:
    """Return the principal that makes the dev proposal: the dev user `member` once they
    logged in, else a stand-in with the sub `seed-member`."""
    sub = await session.scalar(select(PrincipalRow.sub).where(PrincipalRow.email.ilike("member@%")))
    return Principal(
        sub=sub or "seed-member", roles=["member"], permissions=set(permissions_of(["member"]))
    )


STAGE_ORDER = ("idea", "planning", "in_review", "approved", "live", "followup", "archived")
SEED_EXCEPTION = "Entwicklungsdaten ohne Motiv"


def load_definitions(path: Path = SEEDS) -> list[dict[str, Any]]:
    """Read the dossier definitions of the YAML file."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))["events"]


async def seed_mappings(session: AsyncSession, path: Path = MAPPING_SEEDS) -> int:
    """Create the default mappings and the extra rows of the YAML file; return the new count."""
    created = len(await MappingService(session, get_settings(), "seed-dev").create_defaults())
    orgs = {
        slug: id_ for slug, id_ in await session.execute(select(Organization.slug, Organization.id))
    }
    known = set((await session.scalars(select(GroupMapping.oidc_group))).all())
    extra = [
        m
        for m in yaml.safe_load(path.read_text(encoding="utf-8"))["mappings"]
        if m["group"] not in known
    ]
    session.add_all(
        GroupMapping(oidc_group=m["group"], role=m["role"], organization_id=orgs[m["organization"]])
        for m in extra
    )
    await session.flush()
    return created + len(extra)


async def _ids(session: AsyncSession, model: type[Organization] | type[Category]) -> dict[str, Any]:
    return {slug: id_ for slug, id_ in await session.execute(select(model.slug, model.id))}


async def advance(
    session: AsyncSession,
    principal: Principal,
    event: Event,
    stage: str,
    definition: dict[str, Any] | None = None,
) -> None:
    """Move a new dossier to `stage` through the services, as the editors would.

    The follow-up stages use a clock set after the end of the event, because a dossier
    only leaves `live` once it ended. Archiving needs the follow-up (M5): retrospective,
    outcome and a verified howto, which the definition supplies.
    """
    definition = definition or {}
    reached = STAGE_ORDER.index(stage)
    pipeline = PipelineService(session, editor_four_eyes=False)
    if reached >= 1:
        await pipeline.stage_fire(principal, event.id, "T01")
    if reached >= 2:
        await grant_image_exception(session, principal, event.id, SEED_EXCEPTION)
        await pipeline.stage_fire(principal, event.id, "T02")
    if reached >= 3:
        await seed_followup.confirm_free_venue(session, principal, event)
        await pipeline.stage_fire(principal, event.id, "T04")
    if reached >= 4:
        await pipeline.stage_fire(principal, event.id, "T05")
    if reached >= 5:
        await pipeline.stage_system_fire(event.id, "T08", event.ends_at + timedelta(hours=13))
    if reached >= 6:
        await seed_followup.fill_followup(session, principal, event, definition)
        await pipeline.stage_fire(principal, event.id, "T09")
        if definition.get("archivedDaysAgo"):
            await seed_followup.move_into_the_past(session, event, definition["archivedDaysAgo"])


async def seed_event(
    session: AsyncSession, principal: Principal, definition: dict[str, Any], ids: dict[str, dict]
) -> bool:
    """Create one dossier and move it to its stage. Return `False` when it exists.

    A definition without `organization` is a proposal of the dev member.
    """
    slug = definition.get("organization")
    organization_id = ids["organization"][slug] if slug else None
    exists = await session.scalar(
        select(Event.id).where(
            Event.organization_id.is_(None)
            if organization_id is None
            else Event.organization_id == organization_id,
            Event.title == definition["title"],
        )
    )
    if exists is not None:
        return False
    start = (utcnow() + timedelta(days=definition["startsInDays"])).replace(
        minute=0, second=0, microsecond=0
    )
    author = principal if organization_id else await seed_member(session)
    created = await EventService(session).create(
        author,
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
    await seed_followup.put_format(session, principal, created, definition)
    await advance(session, principal, created, definition.get("stage", "idea"), definition)
    return True


async def main() -> int:
    """Seed the database of `DATABASE_URL` and return the number of new dossiers."""
    async with get_sessionmaker()() as session:
        await ensure_reference(session)
        print(f"seeded {await seed_mappings(session)} new group mapping(s)")
        ids = {
            "organization": await _ids(session, Organization),
            "category": await _ids(session, Category),
        }
        principal = seed_editor()
        results = [await seed_event(session, principal, d, ids) for d in load_definitions()]
        await seed_followup.master_howto(session, principal, "movienight")
        await session.commit()
    return sum(results)


if __name__ == "__main__":
    print(f"seeded {asyncio.run(main())} new dossier(s)")
