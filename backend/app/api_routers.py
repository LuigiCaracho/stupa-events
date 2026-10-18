"""The routers of the API, in one list.

`create_app` mounts every router below under `/api`. A module adds its router here, and
`tests/unit/test_route_authz_inventory.py` then checks that every route of it declares a
permission gate or sits in the public allowlist.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.dossier.router import router as dossier_router
from app.modules.events.router import router as events_router
from app.modules.orgs.router import router as orgs_router
from app.modules.pipeline.router import router as pipeline_router
from app.modules.publicapi.router import router as public_router
from app.modules.taxonomy.router import router as taxonomy_router

ROUTERS: tuple[APIRouter, ...] = (
    auth_router,
    audit_router,
    orgs_router,
    taxonomy_router,
    events_router,
    pipeline_router,
    dossier_router,
    public_router,
)
