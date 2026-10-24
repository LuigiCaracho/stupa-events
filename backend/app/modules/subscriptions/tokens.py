"""Tokens of the subscription flows: confirmation, management link and calendar address.

A token is 256 bits of randomness (43 URL-safe characters). The database keeps only its
SHA-256 hex digest and compares by equality on that digest, so a lookup reveals nothing
about a near miss and a leaked table gives no usable token.
"""

from __future__ import annotations

import hashlib
import re
import secrets

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
CONFIRM_TTL_HOURS = 24
MANAGE_TTL_HOURS = 2


def new_token() -> str:
    """Return a fresh random token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest that the database stores for `token`."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_well_formed(token: str) -> bool:
    """Tell whether `token` has the shape of a token this module issues."""
    return TOKEN_PATTERN.fullmatch(token) is not None
