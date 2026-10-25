"""Audited actions.

This is the closed catalog of security-relevant and state-relevant operations. Modules
reference these constants instead of free-form strings. That keeps the ``action`` values
stable and queryable. ``data`` carries only id references and metadata, never PII.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/audit/actions.py (events catalog)
"""

from __future__ import annotations

from enum import StrEnum


class AuditAction(StrEnum):
    """Stable ``audit_entry.action`` keys."""

    # A successful OIDC login. ``data`` holds only ``{"method": "oidc"}``: never an IP
    # address, a user agent or an e-mail. A refused login writes nothing.
    LOGIN = "login"
    EVENT_CREATE = "event_create"
    EVENT_UPDATE = "event_update"
    # A state change of the dossier. ``data`` carries the action and the two states.
    EVENT_TRANSITION = "event_transition"
    EVENT_CANCEL = "event_cancel"
    EVENT_POSTPONE = "event_postpone"
    EVENT_REINSTATE = "event_reinstate"
    EVENT_REVERT = "event_revert"
    # M5: ids only, never amounts or texts.
    EVENT_CLONE = "event_clone"
    EVENT_OUTCOME = "event_outcome"
    EVENT_HOWTO_VERIFY = "event_howto_verify"
    EVENT_LOCATION_CONFIRM = "event_location_confirm"
    EVENT_FACTS = "event_facts"
    FORMAT_CREATE = "format_create"
    FORMAT_UPDATE = "format_update"
    ATTACHMENT_UPLOAD = "attachment_upload"
    ATTACHMENT_QUARANTINE = "attachment_quarantine"
    ATTACHMENT_SCAN = "attachment_scan"
    ATTACHMENT_REPLACE = "attachment_replace"
    ATTACHMENT_UPDATE = "attachment_update"
    ATTACHMENT_RETIRE = "attachment_retire"
    ATTACHMENT_RESCAN = "attachment_rescan"
    DOCUMENT_CREATE = "document_create"
    DOCUMENT_UPDATE = "document_update"
    COMMENT_CREATE = "comment_create"
    COMMENT_RESOLVE = "comment_resolve"
    COMMENT_REOPEN = "comment_reopen"
    CHECKLIST_CHANGE = "checklist_change"
    QUOTE_CHANGE = "quote_change"
    ROLE_MAPPING_CHANGE = "role_mapping_change"
    # A membership row that the OIDC sync added or removed.
    ROLE_CHANGE = "role_change"
    SESSION_REVOKE = "session_revoke"
    CONFIG_CHANGE = "config_change"
    # A geocode request for a venue: carries the venue id and `found`, never the address.
    VENUE_GEOCODE = "venue_geocode"
    EXPORT = "export"
