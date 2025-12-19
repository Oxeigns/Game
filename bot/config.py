import os
from typing import List

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "telegram_bot")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
LOGS_GROUP_ID = int(os.getenv("LOGS_GROUP_ID", "0")) or None
DEFAULT_ECONOMY_ENABLED = os.getenv("DEFAULT_ECONOMY_ENABLED", "true").lower() == "true"
MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "false").lower() == "true"

CD_DAILY = int(os.getenv("CD_DAILY", "86400"))
CD_ROB = int(os.getenv("CD_ROB", "1800"))
CD_KILL = int(os.getenv("CD_KILL", "1800"))
CD_GIVE = int(os.getenv("CD_GIVE", "600"))
CD_PROTECT = int(os.getenv("CD_PROTECT", "86400"))
CD_REVIVE = int(os.getenv("CD_REVIVE", "600"))
CD_BROADCAST = int(os.getenv("CD_BROADCAST", "3600"))
CD_PANEL = int(os.getenv("CD_PANEL", "60"))

COOLDOWNS = {
    "daily": CD_DAILY,
    "rob": CD_ROB,
    "kill": CD_KILL,
    "give": CD_GIVE,
    "protect": CD_PROTECT,
    "revive": CD_REVIVE,
    "broadcast": CD_BROADCAST,
    "panel": CD_PANEL,
}

# Broadcast throttling (seconds)
BROADCAST_DELAY = float(os.getenv("BROADCAST_DELAY", "0.05"))

# RetryAfter max wait safeguard
MAX_RETRY_AFTER = int(os.getenv("MAX_RETRY_AFTER", "5"))

SUDO_USERS: List[int] = []
if os.getenv("SUDO_USERS"):
    try:
        SUDO_USERS = [int(x) for x in os.getenv("SUDO_USERS", "").split(",") if x.strip()]
    except ValueError:
        SUDO_USERS = []

TIME_FORMAT = "%Y-%m-%d %H:%M:%S UTC"

