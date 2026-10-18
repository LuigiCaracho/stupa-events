"""Model aggregator.

This module imports the `models` module of every package under `app.modules`, so
`Base.metadata` is complete. That metadata is the single source for Alembic and for the
tests. A new module needs no entry here: it only needs a `models.py`.

Copied from STUPA-Workflow@93c33d6 backend/app/models.py (discovery instead of a list)
"""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil

import app.modules
from app.db import Base


def import_all_models() -> list[str]:
    """Import every `app.modules.<name>.models` and return the module names."""
    loaded: list[str] = []
    for info in pkgutil.iter_modules(app.modules.__path__):
        name = f"app.modules.{info.name}.models"
        if importlib.util.find_spec(name) is not None:
            importlib.import_module(name)
            loaded.append(name)
    return sorted(loaded)


LOADED_MODEL_MODULES = import_all_models()

__all__ = ["LOADED_MODEL_MODULES", "Base", "import_all_models"]
