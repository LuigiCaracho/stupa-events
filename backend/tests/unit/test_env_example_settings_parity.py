"""Keep `deploy/.env.example` and `app.settings.Settings` in step.

`Settings` uses `extra="ignore"`, so a key that the template documents under a name no
field reads is dropped without a word. The template belongs to the infra builder; the
test skips until the file exists.

Copied from STUPA-Workflow@93c33d6 backend/tests/unit/test_env_example_settings_parity.py (events)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import AliasChoices

from app.settings import Settings

_EXAMPLE_PATH = Path(__file__).resolve().parents[3] / "deploy" / ".env.example"

pytestmark = pytest.mark.skipif(
    not _EXAMPLE_PATH.exists(), reason="deploy/.env.example is not there yet"
)

_NOT_READ_BY_THE_API = {
    "POSTGRES_DB": "postgres image",
    "POSTGRES_USER": "postgres image",
    "POSTGRES_PASSWORD": "postgres image",
    "EVENTS_APP_PASSWORD": "compose, role setup",
    "EVENTS_MIGRATOR_PASSWORD": "compose, role setup",
    "EVENTS_PUBLIC_PASSWORD": "compose, role setup",
    "MINIO_ROOT_USER": "minio image",
    "MINIO_ROOT_PASSWORD": "minio image",
    "TRUSTED_PROXY_IP": "compose interpolation (nginx real-ip template)",
    "WEB_PORT": "compose interpolation",
    "WEB_HOST": "compose interpolation",
    "ENV_FILE": "compose interpolation",
}

_KEY_RE = re.compile(r"^\s*(?:#\s*)?([A-Z][A-Z0-9_]*)=", re.MULTILINE)


def _example_keys() -> set[str]:
    return set(_KEY_RE.findall(_EXAMPLE_PATH.read_text(encoding="utf-8")))


def _settings_env_names() -> set[str]:
    names: set[str] = set()
    for name, field in Settings.model_fields.items():
        names.add(name.upper())
        alias = field.validation_alias
        if isinstance(alias, AliasChoices):
            names.update(str(c).upper() for c in alias.choices if isinstance(c, str))
        elif isinstance(alias, str):
            names.add(alias.upper())
    return names


def test_every_documented_key_is_read_somewhere() -> None:
    unread = sorted(_example_keys() - _settings_env_names() - set(_NOT_READ_BY_THE_API))
    assert not unread, f"documented but not read by Settings (silently dropped): {unread}"


def test_removed_magic_link_key_is_gone() -> None:
    assert "MAGIC_LINK_SECRET" not in _example_keys()
    assert "MAGIC_LINK_SECRET" not in _settings_env_names()


def test_required_settings_are_documented() -> None:
    required = {"DATABASE_URL", "SESSION_SECRET", "PUBLIC_DATABASE_URL", "ARQ_QUEUE_NAME"}
    assert required <= _example_keys()
