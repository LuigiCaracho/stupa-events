"""Document routes: list, create, read, save with `If-Match`, history, diff and autosave."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.dossier import documents
from app.modules.dossier.capped import capped_route
from app.modules.dossier.models_documents import Document
from app.modules.dossier.schemas_documents import (
    DiffOut,
    DocumentCreate,
    DocumentDraftIn,
    DocumentDraftOut,
    DocumentItem,
    DocumentOut,
    DocumentPut,
    RevisionItem,
    RevisionOut,
)
from app.modules.events.conflict import etag_of, parse_if_match
from app.shared.errors import PreconditionRequiredError, ProblemDetail

MAX_DRAFT_BYTES = 256 * 1024
MAX_SAVE_BYTES = 1536 * 1024
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {
    c: _PROBLEM for c in (401, 403, 404, 409, 413, 422, 428)
}
Reader = Annotated[Principal, Depends(require_principal("library.read"))]
Editor = Annotated[Principal, Depends(require_any_scope("event.edit"))]
IfMatch = Annotated[str | None, Header(alias="If-Match")]

router = APIRouter(tags=["documents"])
draft_router = APIRouter(tags=["documents"], route_class=capped_route(MAX_DRAFT_BYTES))
save_router = APIRouter(tags=["documents"], route_class=capped_route(MAX_SAVE_BYTES))


def _etag(response: Response, row: Document) -> None:
    response.headers["ETag"] = etag_of(row.rev)


def required_rev(if_match: str | None) -> int:
    """Return the revision of `If-Match`; `*` and a missing header are 428."""
    expected = parse_if_match(if_match)
    if expected is None:
        raise PreconditionRequiredError("An If-Match header with the revision is required.")
    return expected


@router.get("/events/{event_id}/documents", response_model=list[DocumentItem], responses=_ERRORS)
async def list_documents(
    db: DbSession, principal: Reader, event_id: UUID, kind: Annotated[str | None, Query()] = None
) -> list[DocumentItem]:
    """List the documents of a dossier without their text."""
    rows = await documents.list_documents(db, principal, event_id, kind)
    return [DocumentItem.model_validate(r) for r in rows]


@router.post(
    "/events/{event_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
async def create_document(
    db: DbSession, principal: Editor, event_id: UUID, body: DocumentCreate, response: Response
) -> DocumentOut:
    """Create a howto or a note; the second howto of a dossier is a 409."""
    row = await documents.create(db, principal, event_id, body)
    out = documents.document_out(row)
    await db.commit()
    _etag(response, row)
    return out


@router.get("/documents/{document_id}", response_model=DocumentOut, responses=_ERRORS)
async def get_document(
    db: DbSession, principal: Reader, document_id: UUID, response: Response
) -> DocumentOut:
    """Return a document with its text and its ETag."""
    row, _ = await documents.load_document(db, principal, document_id, archive=True)
    _etag(response, row)
    return documents.document_out(row)


@save_router.put("/documents/{document_id}", response_model=DocumentOut, responses=_ERRORS)
async def put_document(
    db: DbSession,
    principal: Editor,
    document_id: UUID,
    body: DocumentPut,
    response: Response,
    if_match: IfMatch = None,
) -> DocumentOut:
    """Save a new version; `If-Match` is mandatory, an identical text is a no-op."""
    row, _ = await documents.save(db, principal, document_id, body, required_rev(if_match))
    out = documents.document_out(row)
    await db.commit()
    _etag(response, row)
    return out


@router.get(
    "/documents/{document_id}/revisions", response_model=list[RevisionItem], responses=_ERRORS
)
async def list_revisions(db: DbSession, principal: Reader, document_id: UUID) -> list[RevisionItem]:
    """List the revisions of a document, newest first."""
    return await documents.revisions(db, principal, document_id)


@router.get(
    "/documents/{document_id}/revisions/{rev}", response_model=RevisionOut, responses=_ERRORS
)
async def get_revision(
    db: DbSession, principal: Reader, document_id: UUID, rev: int
) -> RevisionOut:
    """Return one full revision."""
    return RevisionOut.model_validate(await documents.get_revision(db, principal, document_id, rev))


@router.get("/documents/{document_id}/diff", response_model=DiffOut, responses=_ERRORS)
async def diff_document(
    db: DbSession,
    principal: Reader,
    document_id: UUID,
    from_rev: Annotated[int, Query(alias="from", ge=1)],
    to_rev: Annotated[int, Query(alias="to", ge=1)],
) -> DiffOut:
    """Return the line diff between two revisions."""
    return await documents.diff(db, principal, document_id, from_rev, to_rev)


def _draft_out(row: Any) -> DocumentDraftOut:
    return DocumentDraftOut(
        base_rev=row.base_rev,
        body_md=row.fields.get("bodyMd", ""),
        title=row.fields.get("title"),
        updated_at=row.updated_at,
    )


@draft_router.put(
    "/documents/{document_id}/draft", response_model=DocumentDraftOut, responses=_ERRORS
)
async def put_draft(
    db: DbSession,
    principal: Editor,
    document_id: UUID,
    body: DocumentDraftIn,
    if_match: IfMatch = None,
) -> DocumentDraftOut:
    """Store the caller's autosave draft; `If-Match` is the revision it is based on."""
    row = await documents.put_draft(
        db, principal, document_id, required_rev(if_match), body.body_md, body.title
    )
    out = _draft_out(row)
    await db.commit()
    return out


@draft_router.get(
    "/documents/{document_id}/draft",
    response_model=DocumentDraftOut,
    responses={**_ERRORS, 204: {"description": "No draft"}},
)
async def get_draft(
    db: DbSession, principal: Editor, document_id: UUID
) -> DocumentDraftOut | Response:
    """Return the caller's own draft, or 204."""
    row = await documents.get_draft(db, principal, document_id)
    return _draft_out(row) if row is not None else Response(status_code=status.HTTP_204_NO_CONTENT)


@draft_router.delete(
    "/documents/{document_id}/draft", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS
)
async def delete_draft(db: DbSession, principal: Editor, document_id: UUID) -> Response:
    """Discard the caller's draft."""
    await documents.delete_draft(db, principal, document_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
