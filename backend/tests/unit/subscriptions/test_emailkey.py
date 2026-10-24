"""Canonical address, keyed hashes and the refusal of unusable text."""

from __future__ import annotations

import pytest

from app.modules.subscriptions import emailkey
from app.modules.subscriptions.emailkey import InvalidEmailError, canonicalize

KEY = "k" * 32


def test_case_whitespace_and_compatibility_forms_fold() -> None:
    assert canonicalize("  Ada.Lovelace@Example.ORG ") == "ada.lovelace@example.org"
    assert canonicalize("ａｄａ@example.org") == "ada@example.org"


def test_the_domain_becomes_idna_and_the_apostrophe_stays() -> None:
    assert canonicalize("Mia@Bücher.example") == "mia@xn--bcher-kva.example"
    assert canonicalize("O'Brien@example.org") == "o'brien@example.org"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "no-at-sign",
        "a@",
        "@b.org",
        "a b@example.org",
        "a\\b@example.org",
        "a\x00@b.org",
        "a\n@example.org",
        "a@@example.org",
        "x" * 250 + "@example.org",
    ],
)
def test_unusable_text_is_refused(text: str) -> None:
    with pytest.raises(InvalidEmailError):
        canonicalize(text)


def test_the_tag_is_dropped_only_for_the_limit_key() -> None:
    a, b = "ada+1@example.org", "ada+2@example.org"
    assert emailkey.without_tag(a) == "ada@example.org"
    assert emailkey.identity_hmac(KEY, a) != emailkey.identity_hmac(KEY, b)
    assert emailkey.limit_hmac(KEY, a) == emailkey.limit_hmac(KEY, b)
    assert emailkey.limit_hmac(KEY, a) == emailkey.limit_hmac(KEY, "ada@example.org")


def test_the_two_hashes_of_one_address_differ_and_depend_on_the_key() -> None:
    address = "ada@example.org"
    assert emailkey.identity_hmac(KEY, address) != emailkey.limit_hmac(KEY, address)
    assert emailkey.identity_hmac(KEY, address) == emailkey.identity_hmac(KEY, address)
    assert emailkey.identity_hmac(KEY, address) != emailkey.identity_hmac("j" * 32, address)
    assert len(emailkey.identity_hmac(KEY, address)) == 64
