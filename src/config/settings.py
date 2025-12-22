"""Application settings with Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Bot
    bot_token: str = Field(..., description="Telegram Bot API token")
    channel_id: Optional[int] = Field(None, description="Telegram channel ID for broadcasts")

    # Database
    database_url: str = Field(
        "sqlite+aiosqlite:///./data/polydictions.db",
        description="Database connection URL",
    )

    # API Server
    api_host: str = Field("127.0.0.1", description="API server host")
    api_port: int = Field(8765, description="API server port")
    api_secret_key: str = Field(
        ...,
        description="Secret key for API authentication (REQUIRED - set in .env)",
        min_length=32,
    )

    # CORS
    allowed_origins: str = Field(
        "",
        description="Comma-separated list of allowed origins for CORS",
    )
    allowed_extension_ids: str = Field(
        "",
        description="Comma-separated list of allowed Chrome extension IDs",
    )

    # Polymarket API
    polymarket_api_url: str = Field(
        "https://gamma-api.polymarket.com",
        description="Polymarket Gamma API URL",
    )
    polymarket_grok_url: str = Field(
        "https://polymarket.com/api/grok/event-summary",
        description="Polymarket Grok API URL",
    )

    # Rate Limiting
    rate_limit_requests: int = Field(20, description="Max requests per period")
    rate_limit_period: int = Field(60, description="Rate limit period in seconds")

    # Monitoring Intervals (seconds)
    event_check_interval: int = Field(60, description="Event monitoring interval")
    news_check_interval: int = Field(300, description="News monitoring interval")
    alert_check_interval: int = Field(30, description="Price alert check interval")

    # Event Filtering
    high_volume_threshold: int = Field(50000, description="Volume threshold for filtering old events")
    new_event_age_hours: int = Field(48, description="Max age in hours for new events")
    max_seen_events: int = Field(10000, description="Maximum number of seen events to keep")

    # Telegram Limits
    message_max_length: int = Field(4096, description="Maximum Telegram message length")
    message_chunk_size: int = Field(3900, description="Chunk size for long messages")

    # Timeouts (seconds)
    http_timeout: int = Field(30, description="Default HTTP timeout")
    market_context_timeout: int = Field(120, description="Market context API timeout")

    # Logging
    log_level: str = Field("INFO", description="Logging level")
    log_format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )

    # Optional: Sentry
    sentry_dsn: Optional[str] = Field(None, description="Sentry DSN for error tracking")

    # Optional: Redis
    redis_url: Optional[str] = Field(None, description="Redis URL for caching")

    @field_validator("allowed_origins")
    @classmethod
    def parse_allowed_origins(cls, v: str) -> str:
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        """Get allowed origins as a list."""
        if not self.allowed_origins:
            return []
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def allowed_extension_ids_list(self) -> list[str]:
        """Get allowed Chrome extension IDs as a list."""
        if not self.allowed_extension_ids:
            return []
        return [ext_id.strip() for ext_id in self.allowed_extension_ids.split(",") if ext_id.strip()]

    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        path = Path("./data")
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
