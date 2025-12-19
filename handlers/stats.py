from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db import async_session
from repositories import get_or_create_group, get_or_create_user, get_user_group_stats, top_users_for_group
from utils import ensure_group_message, italic

router = Router()


@router.message(Command("points"))
async def points_cmd(message: Message):
    if not message.from_user:
        return
    if not ensure_group_message(message):
        await message.reply(italic("Use this in a group."))
        return
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        group = await get_or_create_group(session, message.chat)
        stats = await get_user_group_stats(session, user, group)
        await session.commit()
    await message.reply(italic(f"You have {user.points} points. Messages in this group: {stats.message_count}."))


@router.message(Command("stats"))
async def stats_cmd(message: Message):
    if not message.from_user:
        return
    if not ensure_group_message(message):
        await message.reply(italic("Use this in a group."))
        return
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        group = await get_or_create_group(session, message.chat)
        stats = await get_user_group_stats(session, user, group)
        await session.commit()
    await message.reply(
        italic(
            f"Points: {user.points}\nMessages (group): {stats.message_count}\nMessages (global): {user.total_messages}"
        )
    )


@router.message(Command("top"))
async def top_cmd(message: Message):
    if not ensure_group_message(message):
        await message.reply(italic("Use this in a group."))
        return
    async with async_session() as session:
        group = await get_or_create_group(session, message.chat)
        top_users = await top_users_for_group(session, group, limit=10)
    lines = ["Top users:"]
    for idx, (user, ug) in enumerate(top_users, start=1):
        name = user.username or user.first_name or "User"
        lines.append(f"{idx}. {name} - {user.points}p, msgs {ug.message_count}")
    await message.reply(italic("\n".join(lines)))
