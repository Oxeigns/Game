import html
import random
from datetime import datetime
from typing import Iterable

from aiogram import Bot
from aiogram.enums import ChatType
from aiogram.types import Message

SAFE_DARES = [
    "Share your favorite productivity tip in the chat.",
    "Compliment someone sincerely.",
    "Recommend a book everyone should read.",
    "Drop a fun fact about space.",
    "Suggest a team playlist song.",
    "Share a quick breathing exercise.",
]


def italic(message: str) -> str:
    return f"<i>{html.escape(message)}</i>"


def format_leaderboard(entries: Iterable[str]) -> str:
    return "\n".join(entries)


def format_user_line(index: int, name: str, points: int, messages: int) -> str:
    return f"{index}. {name} — {points} pts / {messages} msgs"


def format_clan_line(index: int, name: str, score: int, members: int) -> str:
    return f"{index}. {name} — {score} pts ({members} members)"


def extract_name(user) -> str:
    return user.username and f"@{user.username}" or (user.first_name or "User")


def format_stats(stats) -> str:
    return (
        f"Points: {stats.points}\n"
        f"Messages: {stats.message_count}\n"
        f"Hugs: {stats.hugs} | Kisses: {stats.kisses} | Punches: {stats.punches} | Bites: {stats.bites} | Dares: {stats.dares}"
    )


def random_dare() -> str:
    return random.choice(SAFE_DARES)


async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.is_chat_admin()
    except Exception:
        return False


def ensure_group_message(message: Message) -> bool:
    return message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}


def human_latency(start: datetime, end: datetime | None = None) -> int:
    end = end or datetime.utcnow()
    delta = end - start
    return int(delta.total_seconds() * 1000)
