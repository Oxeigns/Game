from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db import async_session
from repositories import get_or_create_group, toggle_leaderboard, top_groups
from scheduler import compose_leaderboard
from utils import ensure_group_message, italic, is_admin

router = Router()


@router.message(Command("topgroups"))
async def top_groups_cmd(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        groups = await top_groups(session)
        await session.commit()
    lines = [f"{idx + 1}. {g.title or 'Group'} — {g.message_count} msgs" for idx, g in enumerate(groups)]
    text = "Top groups:\n" + "\n".join(lines) if lines else "No groups yet."
    await message.reply(italic(text))


@router.message(Command("leaderboard_on"))
async def leaderboard_on_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        return
    async with async_session() as session:
        group = await get_or_create_group(session, message.chat)
        await toggle_leaderboard(session, group, True)
        await session.commit()
    await message.reply(italic("Leaderboards enabled."))


@router.message(Command("leaderboard_off"))
async def leaderboard_off_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        return
    async with async_session() as session:
        group = await get_or_create_group(session, message.chat)
        await toggle_leaderboard(session, group, False)
        await session.commit()
    await message.reply(italic("Leaderboards disabled."))


@router.message(Command("leaderboard_now"))
async def leaderboard_now_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    if not await is_admin(message.bot, message.chat.id, message.from_user.id):
        return
    async with async_session() as session:
        group = await get_or_create_group(session, message.chat)
        text = await compose_leaderboard(session, group)
        await session.commit()
    await message.reply(italic(text))
