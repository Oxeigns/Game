from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db import async_session
from repositories import get_or_create_group, get_or_create_user, get_stats, list_top_users
from utils import extract_name, ensure_group_message, format_stats, format_user_line, italic

router = Router()


@router.message(Command("points"))
async def points_cmd(message: Message):
    if not ensure_group_message(message):
        return
    if not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        group = await get_or_create_group(session, message.chat)
        stats = await get_stats(session, user, group)
        await session.commit()
    await message.reply(italic(f"You have {stats.points} points."))


@router.message(Command("top"))
async def top_cmd(message: Message):
    if not ensure_group_message(message):
        return
    if not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        group = await get_or_create_group(session, message.chat)
        leaders = await list_top_users(session, group, limit=10)
        await session.commit()
    lines = [
        format_user_line(idx + 1, extract_name(user), stats.points, stats.message_count)
        for idx, (stats, user) in enumerate(leaders)
    ]
    text = "Top users:\n" + "\n".join(lines) if lines else "No data yet."
    await message.reply(italic(text))


@router.message(Command("stats"))
async def stats_cmd(message: Message):
    if not ensure_group_message(message):
        return
    if not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        group = await get_or_create_group(session, message.chat)
        stats = await get_stats(session, user, group)
        await session.commit()
    text = f"Your stats:\n{format_stats(stats)}"
    await message.reply(italic(text))
