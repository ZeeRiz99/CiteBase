"""Typed application settings, loaded from environment variables."""

from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    # White-label branding: the product name lives here and nowhere else.
    product_name: str = "CiteBase"
    product_tagline: str = "Ask your documents. Get answers you can verify."
    app_base_url: str = "http://localhost:8080"

    database_url: str
    migrations_database_url: str | None = None
    db_pool_size: int = 5

    secret_key: SecretStr
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    email_verification_ttl_hours: int = 24
    password_reset_ttl_minutes: int = 60
    cookie_secure: bool = True

    email_backend: Literal["smtp", "memory"] = "smtp"
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = False
    email_from: str = "CiteBase <no-reply@citebase.local>"

    rate_limit_enabled: bool = True
    worker_poll_seconds: float = Field(default=1.0, gt=0)

    @field_validator("secret_key")
    @classmethod
    def _secret_key_strength(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return value

    def derive_key(self, purpose: str) -> bytes:
        """Derive an independent key per purpose so one leak does not expose the others."""
        return hmac.new(
            self.secret_key.get_secret_value().encode(), purpose.encode(), hashlib.sha256
        ).digest()


@lru_cache
def get_settings() -> Settings:
    return Settings()
