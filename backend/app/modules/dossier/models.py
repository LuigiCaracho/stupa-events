"""Model aggregator of the dossier package: imports the table modules for `Base.metadata`."""

from __future__ import annotations

from app.modules.dossier import (  # noqa: F401
    models_checklist,
    models_comments,
    models_documents,
    models_quotes,
)
