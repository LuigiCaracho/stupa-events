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
    # A transition of the pipeline. ``data`` carries the transition id and the two states.
    EVENT_TRANSITION = "event_transition"
    EVENT_IMAGE_EXCEPTION = "event_image_exception"
    ATTACHMENT_UPLOAD = "attachment_upload"
    ATTACHMENT_QUARANTINE = "attachment_quarantine"
    ATTACHMENT_SCAN = "attachment_scan"
    ATTACHMENT_REPLACE = "attachment_replace"
    ROLE_MAPPING_CHANGE = "role_mapping_change"
    SESSION_REVOKE = "session_revoke"
    CONFIG_CHANGE = "config_change"
    EXPORT = "export"
