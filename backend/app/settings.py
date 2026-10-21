"""Application settings from `.env` (pydantic-settings).

A required secret has no default. If a secret is missing, `load_settings` raises a
clear `SettingsError` at startup instead of a raw pydantic ValidationError. See
`deploy/.env.example` for the layout and the names.

Copied from STUPA-Workflow@93c33d6 backend/app/settings.py (trimmed to the M1 fields)
"""

import json
import logging
from functools import lru_cache
from typing import Annotated, Any

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_MIN_SECRET_LEN = 16

_log = logging.getLogger("app.settings")

CsvList = Annotated[list[str], NoDecode]


def _split_csv(value: Any) -> Any:
    """Turn a comma-separated (or JSON) env value into a list of trimmed entries."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in text.split(",") if part.strip()]


class SettingsError(RuntimeError):
    """Clear startup error for missing/invalid configuration."""


class Settings(BaseSettings):
    """All environment-driven settings of the API and the worker."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "STUPA Events API"
    app_version: str = "0.0.1"
    environment: str = "development"
    log_level: str = "INFO"
    public_base_url: str = "http://localhost:8081"
    ics_uid_domain: str = "events.reutlingen.university"
    public_snapshot_max_age_seconds: int = 7200
    public_snapshot_max_rows: int = 5000
    local_timezone: str = "Europe/Berlin"

    strict_security: bool = True

    database_url: str
    db_migration_url: str | None = None
    public_database_url: str | None = None
    session_secret: str = Field(min_length=_MIN_SECRET_LEN)

    forwarded_allow_ips: str = "127.0.0.1"

    csrf_enabled: bool = True
    csrf_cookie_name: str = "XSRF-TOKEN"
    csrf_header_name: str = "X-XSRF-TOKEN"

    cors_allow_origins: CsvList = []

    redis_url: str = "redis://redis:6379/0"
    arq_queue_name: str = "events"

    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = Field(default=None, min_length=_MIN_SECRET_LEN)
    oidc_redirect_url: str | None = None
    oidc_scopes: str = "openid email profile offline_access"
    oidc_groups_claim: str = "groups"
    oidc_post_logout_redirect_url: str | None = None

    @field_validator(
        "oidc_issuer",
        "oidc_client_id",
        "oidc_client_secret",
        "oidc_redirect_url",
        "oidc_post_logout_redirect_url",
        "public_database_url",
        mode="before",
    )
    @classmethod
    def _empty_value_is_unset(cls, value: Any) -> Any:
        """Read an empty or blank optional value as not set."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    bootstrap_admin_subjects: str = ""
    bootstrap_admin_emails: str = ""

    @property
    def bootstrap_admin_subject_set(self) -> set[str]:
        """OIDC `sub` values from `BOOTSTRAP_ADMIN_SUBJECTS` (comma-separated, trimmed)."""
        return {s.strip() for s in self.bootstrap_admin_subjects.split(",") if s.strip()}

    @property
    def bootstrap_admin_email_set(self) -> set[str]:
        """Emails from `BOOTSTRAP_ADMIN_EMAILS` (comma-separated, trimmed, lowercased)."""
        return {e.strip().lower() for e in self.bootstrap_admin_emails.split(",") if e.strip()}

    session_cookie_name: str = "ev_session"
    oidc_tx_cookie_name: str = "ev_oidc_tx"
    session_revalidate_hours: int = Field(default=4, ge=1, le=168)
    session_revalidate_grace_hours: int = Field(default=24, ge=1, le=720)
    cookie_secure: bool = True

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seconds: int = 30
    mail_from: str = "noreply@events.local"
    mail_from_name: str = "STUPA Events"
    mail_default_lang: str = "de"
    mail_max_tries: int = 5
    mail_retry_backoff_seconds: int = 30

    @property
    def smtp_enabled(self) -> bool:
        """Report whether the worker really sends mail (needs `smtp_host`)."""
        return bool(self.smtp_host)

    minio_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_bucket: str = "events-attachments"
    minio_public_bucket: str = "events-public"
    minio_secure: bool = False
    attachment_max_bytes: int = 10 * 1024 * 1024
    markdown_image_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1)

    backup_bucket: str = "events-backups"
    backup_age_recipient: str | None = None
    backup_age_identity_file: str | None = None
    backup_retention_count: int = 14

    clamav_host: str | None = None
    clamav_port: int = 3310
    clamav_timeout_seconds: int = 60
    scan_max_tries: int = 5
    scan_retry_backoff_seconds: int = 30

    rate_limit_enabled: bool = True
    rl_attachments_per_hour: int = 30
    rl_media_images_per_hour: int = 120
    rl_search_per_minute: int = 240
    rl_default_write_per_hour: int = 100
    rl_default_write_session_per_hour: int = 3000

    editor_four_eyes: bool = False

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _accept_csv_lists(cls, value: Any) -> Any:
        """Accept a comma-separated list, as `deploy/.env.example` documents it."""
        return _split_csv(value)

    @property
    def storage_enabled(self) -> bool:
        """Object storage is active only when a MinIO endpoint is set."""
        return bool(self.minio_endpoint)

    @property
    def clamav_enabled(self) -> bool:
        """ClamAV scan is active only when a clamd host is set."""
        return bool(self.clamav_host)

    @property
    def is_production(self) -> bool:
        """Report whether the app runs the production profile (`ENVIRONMENT=production`)."""
        return self.environment == "production"

    @property
    def strict_security_enabled(self) -> bool:
        """Report whether the strict hardening guards apply (fail-safe).

        True as soon as `strict_security` is on or `environment` equals "production",
        so a forgotten ENVIRONMENT=production does not silently disable the guards.
        """
        return self.strict_security or self.is_production

    @property
    def oidc_enabled(self) -> bool:
        """OIDC is active only when all required parameters are set."""
        return bool(
            self.oidc_issuer
            and self.oidc_client_id
            and self.oidc_client_secret
            and self.oidc_redirect_url
        )

    @model_validator(mode="after")
    def _no_wildcard_proxy_in_prod(self) -> "Settings":
        """Refuse `FORWARDED_ALLOW_IPS` set to "*" in `production`.

        Raises:
            ValueError: The environment is `production` and `forwarded_allow_ips`
                contains "*".
        """
        if self.environment == "production" and "*" in self.forwarded_allow_ips:
            raise ValueError('FORWARDED_ALLOW_IPS must not be "*" in production.')
        return self

    @model_validator(mode="after")
    def _strict_security_warnings(self) -> "Settings":
        """Warn loudly when the configuration stays weak under hardening."""
        if not self.is_production:
            _log.warning(
                "ENVIRONMENT=%r (not 'production'): production-only security guards "
                "may be disabled.",
                self.environment,
            )
        if self.storage_enabled and not self.clamav_enabled:
            _log.warning(
                "MINIO storage is enabled but CLAMAV is disabled: uploads stay "
                "scanned=False and quarantined. Configure CLAMAV_HOST."
            )
        return self


def load_settings(**overrides: Any) -> Settings:
    """Load the settings.

    Raises:
        SettingsError: A required field is missing, or the configuration is invalid.
            The message names the fields.
    """
    try:
        return Settings(**overrides)
    except ValidationError as exc:
        missing = [
            ".".join(str(p) for p in err["loc"]) for err in exc.errors() if err["type"] == "missing"
        ]
        if missing:
            raise SettingsError(
                "Fehlende Pflicht-Konfiguration (env): " + ", ".join(sorted(missing))
            ) from exc
        raise SettingsError(f"Ungültige Konfiguration: {exc}") from exc


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings of the process."""
    return load_settings()
