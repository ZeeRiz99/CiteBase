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
    invitation_ttl_days: int = 7
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

    # Documents
    storage_dir: str = "/data/storage"
    max_upload_mb: int = Field(default=50, gt=0)  # hard cap; workspaces may set lower
    max_pdf_pages: int = Field(default=500, gt=0)
    extraction_timeout_seconds: int = Field(default=300, gt=0)
    retention_days: int = Field(default=30, ge=0)  # soft-deleted documents are purged after this
    max_image_megapixels: int = Field(default=40, gt=0)  # PNG/JPEG uploads (decompression bombs)

    # Text recognition (Tesseract) for scanned PDF pages and images.
    ocr_enabled: bool = True
    ocr_languages: str = "eng"  # Tesseract codes joined with "+", installed in the image
    ocr_dpi: int = Field(default=300, ge=100, le=600)
    ocr_max_pages: int = Field(default=100, gt=0)  # longer scans are flagged instead of recognized
    ocr_timeout_seconds: int = Field(default=900, gt=0)  # whole document

    # AI providers. Keys come only from the environment; they are never logged or returned.
    gemini_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    # "auto" uses the real provider for the profile/model; "fake" is deterministic (tests, CI).
    embedding_backend: Literal["auto", "fake"] = "auto"
    llm_backend: Literal["auto", "fake"] = "auto"
    default_embedding_profile: int = 2  # see app/rag/profiles.py
    embedder_url: str = "http://embedder:8001"  # local embedding service (profile 1)
    llm_provider: Literal["gemini", "openai", "anthropic"] = "gemini"
    llm_model: str = "gemini-3.5-flash-lite"
    llm_fallback_models: list[str] = Field(default_factory=list)
    llm_cheap_model: str = "gemini-3.5-flash-lite"  # query rewriting, eval judging
    llm_thinking_level: str = "minimal"  # Gemini 3.x: minimal thinking keeps answers fast
    llm_temperature: float = 0.1
    llm_max_output_tokens: int = 1024
    llm_timeout_seconds: float = 60.0

    # Retrieval
    rag_candidates: int = Field(default=30, ge=5, le=100)  # per search method, before fusion
    rag_top_k: int = Field(default=6, ge=1, le=20)

    # Chat
    chat_rate_per_minute: int = Field(default=20, gt=0)  # questions per user per minute
    # Answer + rewrite tokens per workspace per calendar month (UTC). A workspace's own
    # monthly_token_limit overrides it; 0 means unlimited.
    monthly_token_limit: int = Field(default=2_000_000, ge=0)
    chat_history_turns: int = Field(default=6, ge=0, le=20)  # prior messages used for follow-ups
    max_question_chars: int = Field(default=2000, gt=0)

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
