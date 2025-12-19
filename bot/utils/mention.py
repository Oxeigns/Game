"""Helpers to format mentions safely."""
from __future__ import annotations

from aiogram.types import User


def mention_user(user: User) -> str:
    name = user.full_name or user.first_name or "user"
    if user.username:
        return f"@{user.username}"
    return f"[{name}](tg://user?id={user.id})"
