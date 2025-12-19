"""Bot configuration using pydantic settings."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    json_logs: bool = Field(default=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=('.env', '.env.local'), extra="ignore")

    bot_token: str = Field(alias="BOT_TOKEN")
    admin_ids: list[int] = Field(default_factory=list, alias="ADMIN_IDS")

    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

    use_dev_sqlite: bool = Field(default=True, alias="DEV_SQLITE", description="Use SQLite fallback when DATABASE_URL is absent")
    # Choose writable tmp path on Heroku dynos to avoid OperationalError.
    sqlite_path: Path = Field(
        default_factory=lambda: Path("/tmp/dev.sqlite") if "DYNO" in os.environ else Path("./data/dev.sqlite")
    )

    flood_limit_default: int = Field(default=6)
    flood_window_seconds: int = Field(default=10)

    max_warns_default: int = Field(default=3)
    warn_action_default: str = Field(default="mute")
    mute_time_default: int = Field(default=3600)

    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            url = self.database_url
            # Convert sync postgres URLs to asyncpg for SQLAlchemy async engine.
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        if self.use_dev_sqlite:
            return f"sqlite+aiosqlite:///{self.sqlite_path}"
        raise RuntimeError("DATABASE_URL not provided and DEV_SQLITE disabled")

    @property
    def resolved_redis_url(self) -> str:
        return self.redis_url or "redis://localhost:6379/0"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
