from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db import async_session
from models import Clan
from repositories import (
    clan_member_count,
    clan_score,
    create_clan,
    get_clan_by_name,
    get_membership,
    get_or_create_group,
    get_or_create_user,
    get_or_create_stats,
    join_clan,
    leave_clan,
    top_clans,
)
from utils import ensure_group_message, format_clan_line, italic

router = Router()


@router.message(Command("createclan"))
async def create_clan_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2 or not parts[1].strip():
        await message.reply(italic("Provide a clan name."))
        return
    name = parts[1].strip()[:64]
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        group = await get_or_create_group(session, message.chat)
        stats = await get_or_create_stats(session, user, group)
        membership = await get_membership(session, stats)
        if membership:
            await message.reply(italic("Leave your current clan first."))
            return
        existing = await get_clan_by_name(session, group, name)
        if existing:
            await message.reply(italic("Clan name already exists."))
            return
        clan = await create_clan(session, group, name, stats)
        await session.commit()
    await message.reply(italic(f"Clan '{name}' created and you joined."))


@router.message(Command("joinclan"))
async def join_clan_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2 or not parts[1].strip():
        await message.reply(italic("Provide a clan name."))
        return
    name = parts[1].strip()
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        group = await get_or_create_group(session, message.chat)
        stats = await get_or_create_stats(session, user, group)
        membership = await get_membership(session, stats)
        if membership:
            await message.reply(italic("Leave your current clan first."))
            return
        clan = await get_clan_by_name(session, group, name)
        if not clan:
            await message.reply(italic("Clan not found."))
            return
        await join_clan(session, clan, stats)
        await session.commit()
    await message.reply(italic(f"Joined clan {name}."))


@router.message(Command("leaveclan"))
async def leave_clan_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        group = await get_or_create_group(session, message.chat)
        stats = await get_or_create_stats(session, user, group)
        removed = await leave_clan(session, stats)
        await session.commit()
    await message.reply(italic("Left clan." if removed else "Not in a clan."))


@router.message(Command("clan"))
async def clan_info_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        group = await get_or_create_group(session, message.chat)
        stats = await get_or_create_stats(session, user, group)
        membership = await get_membership(session, stats)
        if not membership:
            await message.reply(italic("You are not in a clan."))
            return
        clan = await session.get(Clan, membership.clan_id)
        if not clan:
            await message.reply(italic("Clan not found."))
            return
        score = await clan_score(session, clan)
        members = await clan_member_count(session, clan)
        await session.commit()
    await message.reply(italic(f"Clan {clan.name}: {members} members | Score {score}"))


@router.message(Command("topclans"))
async def top_clans_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        group = await get_or_create_group(session, message.chat)
        clans = await top_clans(session, group)
        await session.commit()
    lines = [format_clan_line(idx + 1, clan.name, score, members) for idx, (clan, score, members) in enumerate(clans)]
    text = "Top clans:\n" + "\n".join(lines) if lines else "No clans yet."
    await message.reply(italic(text))
