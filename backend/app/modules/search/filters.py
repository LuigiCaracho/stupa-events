"""The reader of a search and its filters, reduced to what the SQL needs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.orgs.scope import org_ids_for, readable_org_ids


@dataclass(frozen=True, slots=True)
class Reader:
    """Who searches: the organizations read (`None` for all) and those with team access."""

    sub: str
    scope: frozenset[UUID] | None
    team_orgs: frozenset[UUID] | None


@dataclass(frozen=True, slots=True)
class Filters:
    """The optional narrowing of a search; `clonable` keeps only template dossiers."""

    states: tuple[str, ...] = ()
    org: str | None = None
    year: int | None = None
    category: str | None = None
    format: str | None = None
    kind: str | None = None
    clonable: bool = False


def _frozen(ids: set[UUID] | None) -> frozenset[UUID] | None:
    return None if ids is None else frozenset(ids)


async def reader_of(session: AsyncSession, principal: Principal) -> Reader:
    """Resolve the rights of a principal once: reading scope and `team` documents scope."""
    scope = await readable_org_ids(session, principal)
    submit = await org_ids_for(session, principal, "event.submit")
    restricted = await org_ids_for(session, principal, "dossier.read_restricted")
    team = None if submit is None or restricted is None else submit | restricted
    return Reader(principal.sub, _frozen(scope), _frozen(team))
