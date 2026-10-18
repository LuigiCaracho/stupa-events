"""Catalog of configurable notification kinds.

A *kind* groups mails that belong together. The notification settings of the account
offer exactly these keys. System mails that carry a function (login, data protection)
stay out of the catalog, so a user cannot switch them off. An unknown kind is never
filtered, so a send fails open.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/notifications/kinds.py (reduced to M1)
"""

from __future__ import annotations

NOTIFICATION_KINDS: tuple[str, ...] = (
    # A dossier changed state or was approved, rejected or withdrawn.
    "status_update",
    # A dossier reached a state where the own role can act.
    "task",
    # A new comment on a dossier that concerns the user.
    "comment",
)
