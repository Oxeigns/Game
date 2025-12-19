import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    bot_token: str = os.environ["BOT_TOKEN"]
    mongo_uri: str = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    db_name: str = os.environ.get("DB_NAME", "telegram_economy_bot")
    default_economy_enabled: bool = os.environ.get("DEFAULT_ECONOMY_ENABLED", "true").lower() == "true"

    # Anti-spam cooldowns (seconds)
    cd_daily: int = 5
    cd_rob: int = 5
    cd_kill: int = 5
    cd_give: int = 3
    cd_protect: int = 3
    cd_revive: int = 3

SETTINGS = Settings()
