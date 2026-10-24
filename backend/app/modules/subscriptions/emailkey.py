"""The mail address as key material: canonical form, keyed hash and `pgcrypto` ciphertext.

The address is stored twice, never in clear text: `pgp_sym_encrypt` under `PGCRYPTO_EMAIL_KEY`
(readable only for sending, the data request and the Listmonk sync) and an HMAC-SHA-256 under
`EMAIL_HASH_KEY` (the lookup key). A second HMAC over the address without its `+tag` feeds only
the abuse counter, because `a+1@x` and `a+2@x` are one mailbox for a flood but two identities.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import LargeBinary, Text, bindparam, func
from sqlalchemy.sql.elements import ColumnElement

MAX_LENGTH = 254
_FORBIDDEN = re.compile(r"[\x00-\x1f\x7f\\]")
_LIMIT_PREFIX = b"limit\x1f"


class InvalidEmailError(ValueError):
    """The text is not a usable mail address."""


def canonicalize(address: str) -> str:
    """Return the canonical form: NFKC, lower-case local part, IDNA lower-case domain.

    Raises:
        InvalidEmailError: The text is too long, holds control characters or a backslash,
            or is not a mail address.
    """
    text = unicodedata.normalize("NFKC", address.strip())
    if not text or len(text) > MAX_LENGTH or _FORBIDDEN.search(text):
        raise InvalidEmailError("not a mail address")
    try:
        parsed = validate_email(text, check_deliverability=False, allow_smtputf8=True)
    except EmailNotValidError as exc:
        raise InvalidEmailError("not a mail address") from exc
    return f"{parsed.local_part.lower()}@{parsed.ascii_domain.lower()}"


def without_tag(canonical: str) -> str:
    """Drop the `+tag` of the local part (`a+1@x` becomes `a@x`)."""
    local, _, domain = canonical.rpartition("@")
    return f"{local.partition('+')[0]}@{domain}"


def _hmac(key: str, data: bytes) -> str:
    return hmac.new(key.encode("utf-8"), data, hashlib.sha256).hexdigest()


def identity_hmac(key: str, canonical: str) -> str:
    """Return the lookup key of a mailbox (keeps the `+tag`)."""
    return _hmac(key, canonical.encode("utf-8"))


def limit_hmac(key: str, canonical: str) -> str:
    """Return the key of the per-address abuse counter (without the `+tag`)."""
    return _hmac(key, _LIMIT_PREFIX + without_tag(canonical).encode("utf-8"))


def encrypt(address: str, key: str) -> ColumnElement[bytes]:
    """Return the SQL expression that encrypts `address` under `key`."""
    return func.pgp_sym_encrypt(
        bindparam(None, address, type_=Text), bindparam(None, key, type_=Text), type_=LargeBinary
    )


def decrypt(column: ColumnElement[bytes], key: str) -> ColumnElement[str]:
    """Return the SQL expression that decrypts `column` under `key`."""
    return func.pgp_sym_decrypt(column, bindparam(None, key, type_=Text), type_=Text)
