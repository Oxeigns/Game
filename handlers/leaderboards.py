from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db import async_session
from repositories import get_or_create_group, set_group_leaderboard, top_clans, top_groups, top_users_for_group
from utils import ensure_group_message, italic

router = Router()


async def _is_admin(message: Message) -> bool:
    if not message.from_user:
        return False
    try:
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        return member.is_chat_admin() or member.status in {"administrator", "creator"}
    except Exception:
        return False


async def build_leaderboard_text(chat_id: int) -> str:
    async with async_session() as session:
        group = await get_or_create_group(session, type("obj", (), {"id": chat_id, "title": ""}))
        users = await top_users_for_group(session, group, limit=5)
        clans = await top_clans(session, limit=5)
        groups = await top_groups(session, limit=5)
    lines = ["🏆 Top Users:"]
    for idx, (user, stats) in enumerate(users, start=1):
        name = user.username or user.first_name or "User"
        lines.append(f"{idx}. {name} - {user.points}p, msgs {stats.message_count}")
    lines.append("\n🏰 Top Clans:")
    for idx, clan in enumerate(clans, start=1):
        lines.append(f"{idx}. {clan.name} - {clan.score}")
    lines.append("\n🌍 Top Groups:")
    for idx, group in enumerate(groups, start=1):
        lines.append(f"{idx}. {group.title} - {group.total_messages} msgs")
    return "\n".join(lines)


@router.message(Command("leaderboard_on"))
async def leaderboard_on(message: Message):
    if not ensure_group_message(message) or not await _is_admin(message):
        return
    async with async_session() as session:
        group = await get_or_create_group(session, message.chat)
        await set_group_leaderboard(session, group, True)
        await session.commit()
    await message.reply(italic("Leaderboards enabled."))


@router.message(Command("leaderboard_off"))
async def leaderboard_off(message: Message):
    if not ensure_group_message(message) or not await _is_admin(message):
        return
    async with async_session() as session:
        group = await get_or_create_group(session, message.chat)
        await set_group_leaderboard(session, group, False)
        await session.commit()
    await message.reply(italic("Leaderboards disabled."))


@router.message(Command("leaderboard_now"))
async def leaderboard_now(message: Message):
    if not ensure_group_message(message):
        return
    text = await build_leaderboard_text(message.chat.id)
    await message.reply(italic(text))


@router.message(Command("topgroups"))
async def topgroups_cmd(message: Message):
    async with async_session() as session:
        groups = await top_groups(session, limit=10)
    lines = ["Top groups:"]
    for idx, group in enumerate(groups, start=1):
        lines.append(f"{idx}. {group.title} - {group.total_messages} msgs")
    await message.reply(italic("\n".join(lines)))
