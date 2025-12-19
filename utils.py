from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from aiogram.types import Message, User as TgUser


def italic(text: str) -> str:
    return f"<i>{text}</i>"


def extract_name(user: TgUser | None) -> str:
    if not user:
        return "User"
    if user.username:
        return f"@{user.username}"
    return (user.first_name or "User").strip()


def ensure_group_message(message: Message) -> bool:
    return message.chat.type in {"group", "supergroup"}


def consecutive_streak(days: list[date]) -> int:
    if not days:
        return 0
    unique_days = sorted(set(days), reverse=True)
    streak = 0
    cursor = date.today()
    for d in unique_days:
        if d == cursor:
            streak += 1
            cursor = cursor - timedelta(days=1)
        elif d < cursor:
            break
    return streak


async def run_periodic(interval: int, coro):
    while True:
        await coro()
        await asyncio.sleep(interval)
