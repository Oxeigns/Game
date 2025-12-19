import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


def _bool_env(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).lower() in {"1", "true", "yes", "on"}


def _int_env(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except ValueError:
        return default


def _list_env(key: str) -> List[int]:
    raw = os.environ.get(key, "")
    vals = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            vals.append(int(item))
        except ValueError:
            continue
    return vals


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.environ.get("BOT_TOKEN", "")
    mongo_uri: str = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    db_name: str = os.environ.get("DB_NAME", "telegram_economy_bot")
    default_economy_enabled: bool = _bool_env("DEFAULT_ECONOMY_ENABLED", True)

    owner_id: int = _int_env("OWNER_ID", 0)
    sudo_users: List[int] = field(default_factory=lambda: _list_env("SUDO_USERS"))
    logs_group_id: int = _int_env("LOGS_GROUP_ID", 0)

    maintenance_mode: bool = _bool_env("MAINTENANCE_MODE", False)

    # cooldowns in seconds
    cd_daily: int = _int_env("COOLDOWN_DAILY", 5)
    cd_rob: int = _int_env("COOLDOWN_ROB", 5)
    cd_kill: int = _int_env("COOLDOWN_KILL", 5)
    cd_give: int = _int_env("COOLDOWN_GIVE", 3)
    cd_protect: int = _int_env("COOLDOWN_PROTECT", 3)
    cd_revive: int = _int_env("COOLDOWN_REVIVE", 3)
    cd_broadcast: int = _int_env("COOLDOWN_BROADCAST", 10)

    broadcast_rate_limit: float = float(os.environ.get("BROADCAST_RATE_PER_SEC", 20))


SETTINGS = Settings()
