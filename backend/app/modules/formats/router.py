"""Format routes (I18): list, page, create, change, master howto, verify, new edition."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.archive.schemas import CloneOut
from app.modules.events.conflict import require_if_match, set_etag, with_current
from app.modules.events.postcommit import invalidate_public
from app.modules.events.presenter import present
from app.modules.events.schemas import EventOut
from app.modules.formats import queries, service
from app.modules.formats.access import ensure_can_manage
from app.modules.formats.howto import create_master
from app.modules.formats.schemas import (
    FormatCard,
    FormatCreate,
    FormatLinkIn,
    FormatOut,
    FormatPatch,
    HowtoCreate,
    MasterHowtoOut,
    NewEditionIn,
    SaveAsFormatIn,
)
from app.shared.errors import ProblemDetail
from app.shared.paging import DEFAULT_LIMIT, MAX_LIMIT, Page

router = APIRouter(tags=["formats"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {c: _PROBLEM for c in (401, 403, 404, 409, 422, 428)}
Reader = Annotated[Principal, Depends(require_principal("library.read"))]
Manager = Annotated[Principal, Depends(require_any_scope("format.manage", "event.publish"))]
Creator = Annotated[Principal, Depends(require_any_scope("event.create"))]
Editor = Annotated[Principal, Depends(require_any_scope("event.edit"))]
IfMatch = Annotated[str | None, Header(alias="If-Match")]


def _pool(request: Request) -> object | None:
    return getattr(request.app.state, "arq_pool", None)


@router.get("/formats", response_model=Page[FormatCard], responses=_ERRORS)
async def list_formats(
    db: DbSession,
    principal: Reader,
    q: Annotated[str | None, Query(max_length=200)] = None,
    organization: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[FormatCard]:
    """List the active formats with their freshness and edition counts."""
    cards, total = await queries.list_cards(
        db, principal, q=q, organization=organization, limit=limit, offset=offset
    )
    return Page(items=cards, total=total, limit=limit, offset=offset)


@router.get("/formats/{slug}", response_model=FormatOut, responses=_ERRORS)
async def get_format(db: DbSession, principal: Reader, slug: str) -> FormatOut:
    """Show a format: master howto, checklist template, mail templates and editions."""
    return await service.format_out(db, principal, await service.load_format(db, slug))


@router.post(
    "/formats", response_model=FormatOut, status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
async def create_format(
    request: Request, db: DbSession, principal: Manager, body: FormatCreate, response: Response
) -> FormatOut:
    """Create a format (409 `slug_taken`)."""
    fmt = await service.create_format(db, principal, body)
    out = await service.format_out(db, principal, fmt)
    await db.commit()
    response.headers["Location"] = f"/api/formats/{fmt.slug}"
    return out


@router.patch("/formats/{slug}", response_model=FormatOut, responses=_ERRORS)
async def patch_format(
    request: Request, db: DbSession, principal: Manager, slug: str, body: FormatPatch
) -> FormatOut:
    """Change title, defaults, description or `active`; the last writer wins."""
    fmt = await service.patch_format(db, principal, slug, body)
    out = await service.format_out(db, principal, fmt)
    await db.commit()
    await invalidate_public(_pool(request))
    return out


@router.post(
    "/formats/{slug}/howto",
    response_model=MasterHowtoOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
async def create_howto(
    db: DbSession, principal: Manager, slug: str, body: HowtoCreate
) -> MasterHowtoOut:
    """Create the master howto from a scaffold or from the howto of a readable dossier."""
    fmt = await service.load_format(db, slug)
    await ensure_can_manage(db, principal, fmt)
    doc = await create_master(db, principal, fmt, body.from_event_id)
    out = MasterHowtoOut(
        id=doc.id,
        rev=doc.rev,
        title=doc.title,
        verified_at=doc.verified_at,
        verified_by=doc.verified_by,
        body_md=doc.body_md,
    )
    await db.commit()
    return out


@router.post("/formats/{slug}/verify", response_model=FormatOut, responses=_ERRORS)
async def verify_format(db: DbSession, principal: Manager, slug: str) -> FormatOut:
    """Date the format and its master howto as verified."""
    fmt = await service.mark_verified(db, principal, slug)
    out = await service.format_out(db, principal, fmt)
    await db.commit()
    return out


@router.post(
    "/formats/{slug}/new-edition",
    response_model=CloneOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
async def new_edition(
    db: DbSession, principal: Creator, slug: str, body: NewEditionIn, response: Response
) -> CloneOut:
    """Start the next edition from the newest template of the format, else from its defaults."""
    result = await service.new_edition(db, principal, slug, body)
    out = (await present(db, principal, [result.event]))[0]
    out.checklist_recomputed = result.recomputed
    await db.commit()
    response.headers["Location"] = f"/api/events/{out.id}"
    return CloneOut(event=out, report=result.report)


@router.post(
    "/events/{event_id}/save-as-format",
    response_model=FormatOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
async def save_as_format(
    request: Request,
    db: DbSession,
    principal: Manager,
    event_id: UUID,
    body: SaveAsFormatIn,
    response: Response,
) -> FormatOut:
    """Turn a dossier into the first edition of a new format."""
    fmt, _ = await service.save_as_format(db, principal, event_id, body)
    out = await service.format_out(db, principal, fmt)
    await db.commit()
    await invalidate_public(_pool(request))
    response.headers["Location"] = f"/api/formats/{fmt.slug}"
    return out


@router.put("/events/{event_id}/format", response_model=EventOut, responses=_ERRORS)
async def put_event_format(
    request: Request,
    db: DbSession,
    principal: Editor,
    event_id: UUID,
    body: FormatLinkIn,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Put a dossier into a format by slug (`{"slug": "movienight"}`) or out of it (`null`)."""
    async with with_current(db, principal):
        event = await service.set_event_format(
            db, principal, event_id, body.slug, require_if_match(if_match)
        )
    out = (await present(db, principal, [event]))[0]
    await db.commit()
    set_etag(response, out.rev)
    await invalidate_public(_pool(request))
    return out
