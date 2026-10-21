"""The routers of the API, in one list.

`create_app` mounts every router below under `/api`. A module adds its router here, and
`tests/unit/test_route_authz_inventory.py` then checks that every route of it declares a
permission gate or sits in the public allowlist.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.account.router import router as account_router
from app.modules.admin.mappings_router import router as mappings_router
from app.modules.admin.principals_router import router as principals_router
from app.modules.admin.taxonomy_router import ROUTERS as ADMIN_TAXONOMY_ROUTERS
from app.modules.archive.router import router as archive_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.dossier.routers import ROUTERS as DOSSIER_ROUTERS
from app.modules.events.drafts_router import router as drafts_router
from app.modules.events.facts_router import router as facts_router
from app.modules.events.location_router import router as location_router
from app.modules.events.revisions_router import router as revisions_router
from app.modules.events.router import router as events_router
from app.modules.followup.router import router as followup_router
from app.modules.formats.router import router as formats_router
from app.modules.library.router import router as library_router
from app.modules.notifications.router import router as notifications_router
from app.modules.orgs.router import router as orgs_router
from app.modules.pipeline.actions_router import alias_router as image_exception_alias_router
from app.modules.pipeline.actions_router import router as actions_router
from app.modules.pipeline.router import router as pipeline_router
from app.modules.publicapi.router import router as public_router
from app.modules.search.router import router as search_router
from app.modules.tasks.router import router as tasks_router
from app.modules.taxonomy.router import router as taxonomy_router

ROUTERS: tuple[APIRouter, ...] = (
    auth_router,
    audit_router,
    mappings_router,
    principals_router,
    *ADMIN_TAXONOMY_ROUTERS,
    orgs_router,
    taxonomy_router,
    events_router,
    drafts_router,
    revisions_router,
    pipeline_router,
    actions_router,
    location_router,
    facts_router,
    followup_router,
    search_router,
    formats_router,
    archive_router,
    library_router,
    image_exception_alias_router,
    tasks_router,
    notifications_router,
    account_router,
    *DOSSIER_ROUTERS,
    public_router,
)
