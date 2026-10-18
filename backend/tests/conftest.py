"""Pytest fixtures: required environment first, then the app and its test clients.

Settings fail at import time without the required variables, so this module sets them
before it imports the app. A developer's `backend/.env` is ignored, so the suite only sees
the environment it sets. The unit suite runs with rate limiting off.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://app:pw@localhost/events_test")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient

from app.settings import Settings

Settings.model_config["env_file"] = None

from app.main import create_app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """A client on a fresh app."""
    return TestClient(create_app())
