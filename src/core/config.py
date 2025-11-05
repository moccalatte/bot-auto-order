"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration model."""

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_admin_ids: List[int] = Field(
        default_factory=list, alias="TELEGRAM_ADMIN_IDS"
    )
    telegram_owner_ids: List[int] = Field(
        default_factory=list, alias="TELEGRAM_OWNER_IDS"
    )
    database_url: str = Field(..., alias="DATABASE_URL")
    pakasir_project_slug: str = Field(..., alias="PAKASIR_PROJECT_SLUG")
    pakasir_api_key: str = Field(..., alias="PAKASIR_API_KEY")
    pakasir_public_domain: str = Field(
        default="https://pots.my.id", alias="PAKASIR_PUBLIC_DOMAIN"
    )
    pakasir_webhook_secret: str | None = Field(
        default=None, alias="PAKASIR_WEBHOOK_SECRET"
    )
    bot_timezone: str = Field(default="Asia/Jakarta", alias="BOT_TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    store_name: str = Field(default="Bot Auto Order", alias="BOT_STORE_NAME")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("telegram_admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> List[int]:
        if value in (None, "", []):
            return []
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [int(item) for item in value]
        raise ValueError("Invalid TELEGRAM_ADMIN_IDS value")

    @field_validator("telegram_owner_ids", mode="before")
    @classmethod
    def parse_owner_ids(cls, value: object) -> List[int]:
        return cls.parse_admin_ids(value)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
