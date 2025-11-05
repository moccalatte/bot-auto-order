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
    data_encryption_key: str | None = Field(default=None, alias="DATA_ENCRYPTION_KEY")
    owner_bot_token: str | None = Field(default=None, alias="OWNER_BOT_TOKEN")
    snk_retention_days: int = Field(default=30, alias="SNK_RETENTION_DAYS")
    enable_owner_alerts: bool = Field(default=False, alias="ENABLE_OWNER_ALERTS")
    owner_alert_threshold: str = Field(default="ERROR", alias="OWNER_ALERT_THRESHOLD")
    health_cpu_threshold: int = Field(default=80, alias="HEALTH_CPU_THRESHOLD")
    health_memory_threshold: int = Field(default=80, alias="HEALTH_MEMORY_THRESHOLD")
    health_disk_threshold: int = Field(default=85, alias="HEALTH_DISK_THRESHOLD")
    log_usage_threshold_mb: int = Field(default=512, alias="LOG_USAGE_THRESHOLD_MB")
    enable_auto_healthcheck: bool = Field(default=True, alias="ENABLE_AUTO_HEALTHCHECK")
    healthcheck_interval_minutes: int = Field(
        default=5, alias="HEALTHCHECK_INTERVAL_MINUTES"
    )
    enable_auto_backup: bool = Field(default=False, alias="ENABLE_AUTO_BACKUP")
    backup_time: str = Field(default="00:00", alias="BACKUP_TIME")
    backup_automatic_offsite: bool = Field(
        default=True, alias="BACKUP_AUTOMATIC_OFFSITE"
    )

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
        if isinstance(value, int):
            return [value]
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
