"""The routers of the taxonomy admin API: organizations, categories and venues.

They are listed, not nested with `include_router`, so the route inventory sees the plain
routes of each one.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.admin.categories_router import router as categories_router
from app.modules.admin.organizations_router import router as organizations_router
from app.modules.admin.venues_router import router as venues_router

ROUTERS: tuple[APIRouter, ...] = (organizations_router, categories_router, venues_router)
