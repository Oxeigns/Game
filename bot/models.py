from __future__ import annotations

from datetime import datetime
from datetime import datetime
from typing import Dict, Optional

from . import config


def default_user(user_id: int, username: str | None = "") -> Dict:
    return {
        "user_id": user_id,
        "username": username or "",
        "balance": 0,
        "kills": 0,
        "robbed_count": 0,
        "is_dead": False,
        "protection_until": None,
        "premium": False,
        "daily_last_claim": None,
        "rob_limit_used": 0,
        "kill_limit_used": 0,
        "dm_enabled": False,
        "cooldowns": {},
    }


def default_group(group_id: int) -> Dict:
    return {"group_id": group_id, "economy_enabled": config.DEFAULT_ECONOMY_ENABLED}


def default_settings(owner_id: int, sudo_users: list[int], logs_group_id: Optional[int]):
    return {
        "_id": "settings",
        "owner_id": owner_id,
        "sudo_users": sudo_users,
        "logs_group_id": logs_group_id,
        "maintenance_mode": config.MAINTENANCE_MODE,
        "created_at": datetime.utcnow(),
    }


def default_broadcast_job(job_id: str, by_user: int, text: str, mode: str) -> Dict:
    now = datetime.utcnow()
    return {
        "job_id": job_id,
        "by_user": by_user,
        "text": text,
        "mode": mode,
        "status": "running",
        "started_at": now,
        "finished_at": None,
        "sent_count": 0,
        "failed_count": 0,
    }


FIRST_START_TEXT = (
    "👋 Welcome! Use /start here to enable DM notifications."
)
