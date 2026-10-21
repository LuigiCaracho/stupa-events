"""Catalog of notification kinds (contract M4, 5.7).

A kind groups the notifications that belong together. The account settings offer exactly
these keys. `changes_requested` is essential: the user cannot switch it off. A kind with
`mail = False` only fills the in-app inbox.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/notifications/kinds.py (rewritten for M4)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Kind:
    """One notification kind and its channels."""

    key: str
    mail: bool
    essential: bool = False


KINDS: tuple[Kind, ...] = (
    Kind("review_requested", mail=True),
    Kind("changes_requested", mail=True, essential=True),
    Kind("comment_added", mail=True),
    Kind("comment_resolved", mail=False),
    Kind("transition_done", mail=False),
    Kind("task_assigned", mail=True),
    Kind("checklist_due", mail=True),
    Kind("followup_reminder", mail=True),
    Kind("auto_archived", mail=True),
)

NOTIFICATION_KINDS: tuple[str, ...] = tuple(k.key for k in KINDS)
_BY_KEY: dict[str, Kind] = {k.key: k for k in KINDS}


def kind_of(key: str) -> Kind:
    """Return the kind with this key.

    Raises:
        KeyError: The key names no kind.
    """
    return _BY_KEY[key]


def is_known(key: str) -> bool:
    """Tell whether the key names a kind."""
    return key in _BY_KEY


def is_essential(key: str) -> bool:
    """Tell whether the user cannot switch the kind off."""
    return _BY_KEY[key].essential
