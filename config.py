import os
from functools import lru_cache
from pydantic import BaseSettings, Field
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BOT_", extra="ignore")

    token: str = Field(..., validation_alias="TOKEN")
    database_url: str = Field(
        default=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db"),
        validation_alias="DATABASE_URL",
    )
    admin_ids: str | None = Field(default=None, validation_alias="ADMINS")

    @property
    def admin_list(self) -> list[int]:
        if not self.admin_ids:
            return []
        return [int(x) for x in self.admin_ids.split(",") if x.strip().isdigit()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
