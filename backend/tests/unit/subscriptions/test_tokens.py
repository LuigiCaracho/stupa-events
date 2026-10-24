"""Tokens: shape, uniqueness, digest."""

from __future__ import annotations

import hashlib

from app.modules.subscriptions import tokens


def test_a_token_has_43_url_safe_characters_and_is_never_repeated() -> None:
    issued = {tokens.new_token() for _ in range(200)}
    assert len(issued) == 200
    assert all(len(t) == 43 and tokens.is_well_formed(t) for t in issued)


def test_the_stored_digest_is_the_sha256_hex_and_not_the_token() -> None:
    token = tokens.new_token()
    digest = tokens.hash_token(token)
    assert digest == hashlib.sha256(token.encode()).hexdigest()
    assert token not in digest and len(digest) == 64
    assert tokens.hash_token(token) != tokens.hash_token(tokens.new_token())


def test_malformed_tokens_are_recognised() -> None:
    for bad in ("", "short", "a" * 42, "a" * 44, "a" * 42 + "!", "a" * 42 + "\n", "ä" * 43):
        assert not tokens.is_well_formed(bad)
