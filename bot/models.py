from datetime import datetime
from typing import Any, Dict, Optional, List


def now_utc() -> datetime:
    return datetime.utcnow()


def new_user_doc(user_id: int, username: Optional[str]) -> Dict[str, Any]:
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
        "cooldowns": {
            "daily": None,
            "rob": None,
            "kill": None,
            "give": None,
            "protect": None,
            "revive": None,
            "broadcast": None,
        },
    }


def new_group_doc(group_id: int, economy_enabled: bool) -> Dict[str, Any]:
    return {"group_id": group_id, "economy_enabled": economy_enabled}


def new_settings_doc(owner_id: int, sudo_users: List[int], logs_group_id: int, maintenance_mode: bool) -> Dict[str, Any]:
    return {
        "_id": "settings",
        "owner_id": owner_id,
        "sudo_users": sudo_users,
        "logs_group_id": logs_group_id if logs_group_id else None,
        "maintenance_mode": maintenance_mode,
        "created_at": now_utc(),
    }
