"""All routers of the dossier module, mounted under `/api` by `api_routers`."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.dossier.attachments_router import router as attachments_router
from app.modules.dossier.checklist_router import router as checklist_router
from app.modules.dossier.comments_router import router as comments_router
from app.modules.dossier.documents_router import draft_router, save_router
from app.modules.dossier.documents_router import router as documents_router
from app.modules.dossier.mail_templates_router import router as mail_templates_router
from app.modules.dossier.quotes_router import router as quotes_router
from app.modules.dossier.router import router as poster_router
from app.modules.media.router import router as media_router

ROUTERS: tuple[APIRouter, ...] = (
    poster_router,
    attachments_router,
    documents_router,
    save_router,
    draft_router,
    mail_templates_router,
    checklist_router,
    comments_router,
    quotes_router,
    media_router,
)
