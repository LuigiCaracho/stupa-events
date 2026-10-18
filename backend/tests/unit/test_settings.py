"""Settings: required secrets, optional OIDC values, CSV lists and the proxy guard."""

from __future__ import annotations

import pytest

from app.settings import SettingsError, load_settings
from tests._support.factories import make_settings


def test_missing_required_secret_names_the_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    with pytest.raises(SettingsError, match="session_secret"):
        load_settings(database_url="postgresql+asyncpg://x/y", _env_file=None)


def test_short_secret_is_rejected() -> None:
    with pytest.raises(SettingsError):
        make_settings(session_secret="short")


def test_contract_defaults() -> None:
    s = make_settings()
    assert s.session_cookie_name == "ev_session"
    assert s.oidc_tx_cookie_name == "ev_oidc_tx"
    assert s.session_revalidate_hours == 4
    assert s.session_revalidate_grace_hours == 24
    assert s.minio_bucket == "events-attachments"
    assert s.minio_public_bucket == "events-public"
    assert s.backup_bucket == "events-backups"
    assert s.arq_queue_name == "events"
    assert s.csrf_cookie_name == "XSRF-TOKEN"
    assert s.csrf_header_name == "X-XSRF-TOKEN"
    assert s.editor_four_eyes is False
    assert not hasattr(s, "magic_link_secret")


def test_blank_oidc_values_mean_not_configured() -> None:
    s = make_settings(oidc_issuer=" ", oidc_client_secret="", public_database_url="")
    assert s.oidc_issuer is None
    assert s.oidc_client_secret is None
    assert s.public_database_url is None
    assert not s.oidc_enabled


def test_oidc_enabled_needs_all_four_values() -> None:
    full = {
        "oidc_issuer": "http://idp/realms/x",
        "oidc_client_id": "events",
        "oidc_client_secret": "s" * 16,
        "oidc_redirect_url": "http://localhost/cb",
    }
    assert make_settings(**full).oidc_enabled
    assert not make_settings(**{**full, "oidc_redirect_url": None}).oidc_enabled


def test_csv_lists_and_bootstrap_sets() -> None:
    s = make_settings(
        cors_allow_origins="https://a, https://b",
        bootstrap_admin_subjects="x, y",
        bootstrap_admin_emails="A@B.de,",
    )
    assert s.cors_allow_origins == ["https://a", "https://b"]
    assert s.bootstrap_admin_subject_set == {"x", "y"}
    assert s.bootstrap_admin_email_set == {"a@b.de"}
    assert make_settings(cors_allow_origins='["https://c"]').cors_allow_origins == ["https://c"]


def test_wildcard_proxy_is_refused_in_production_only() -> None:
    assert make_settings(forwarded_allow_ips="*").forwarded_allow_ips == "*"
    with pytest.raises(SettingsError):
        make_settings(environment="production", forwarded_allow_ips="*")


def test_derived_flags() -> None:
    s = make_settings(minio_endpoint="minio:9000", clamav_host="clamav", smtp_host="smtp")
    assert s.storage_enabled and s.clamav_enabled and s.smtp_enabled
    assert s.strict_security_enabled
    assert not make_settings().storage_enabled
    assert make_settings(strict_security=False, environment="production").strict_security_enabled
    assert not make_settings(strict_security=False).strict_security_enabled


def test_storage_without_clamav_warns(caplog: pytest.LogCaptureFixture) -> None:
    make_settings(minio_endpoint="minio:9000")
    assert "CLAMAV is disabled" in caplog.text
