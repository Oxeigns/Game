from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db import async_session
from models import Clan, ClanRole
from repositories import (
    clan_by_name,
    clan_member_count,
    create_clan,
    get_clan_settings,
    get_membership,
    get_or_create_group,
    get_or_create_user,
    get_streak,
    join_clan,
    leave_clan,
    reset_weekly_points,
    set_coleader,
    set_leader_cooldown,
    top_clans,
    update_clan_min_points,
)
from utils import ensure_group_message, extract_name, italic

router = Router()

CLAN_CREATE_MIN_POINTS = 50000
CLAN_CREATE_STREAK = 30


def _role_label(role: ClanRole | None) -> str:
    if role == ClanRole.LEADER:
        return "Leader"
    if role == ClanRole.CO_LEADER:
        return "Co-leader"
    return "Member"


async def _load_clan(session, clan_id: int) -> Clan | None:
    return await session.get(Clan, clan_id)


@router.message(Command("createclan"))
async def create_clan_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        await message.reply(italic("Provide a clan name."))
        return
    name = parts[1].strip()
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        await get_or_create_group(session, message.chat)
        membership = await get_membership(session, user)
        if membership:
            await message.reply(italic("You are already in a clan."))
            return
        streak = await get_streak(session, user)
        if streak < CLAN_CREATE_STREAK or user.points < CLAN_CREATE_MIN_POINTS:
            await message.reply(italic("You need a 30-day streak and 50000 points to create a clan."))
            return
        if await clan_by_name(session, name):
            await message.reply(italic("Clan name already taken."))
            return
        await create_clan(session, name, user)
        await session.commit()
    await message.reply(italic(f"Clan '{name}' created. You are the leader."))


@router.message(Command("joinclan"))
async def join_clan_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        await message.reply(italic("Provide a clan name."))
        return
    name = parts[1].strip()
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        await get_or_create_group(session, message.chat)
        if await get_membership(session, user):
            await message.reply(italic("You are already in a clan."))
            return
        clan = await clan_by_name(session, name)
        if not clan:
            await message.reply(italic("Clan not found."))
            return
        settings = await get_clan_settings(session, clan)
        if user.points < settings.min_join_points:
            await message.reply(italic("You do not meet the clan's minimum points."))
            return
        await join_clan(session, user, clan)
        await session.commit()
    await message.reply(italic(f"Joined clan {name}."))


@router.message(Command("leaveclan"))
async def leave_clan_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        membership = await get_membership(session, user)
        if not membership:
            await message.reply(italic("You are not in a clan."))
            return
        await leave_clan(session, user)
        await session.commit()
    await message.reply(italic("You left your clan."))


@router.message(Command("clan"))
async def clan_info_self(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        membership = await get_membership(session, user)
        if not membership:
            await message.reply(italic("You are not in a clan."))
            return
        clan = await _load_clan(session, membership.clan_id)
        if not clan:
            await message.reply(italic("Clan missing."))
            return
        members = await clan_member_count(session, clan)
        settings = await get_clan_settings(session, clan)
    await message.reply(
        italic(
            f"Clan: {clan.name}\nRole: {_role_label(membership.role)}\nScore: {clan.score}\nMembers: {members}\nMin join: {settings.min_join_points}"
        )
    )


@router.message(Command("clans"))
async def clans_cmd(message: Message):
    async with async_session() as session:
        clans = await top_clans(session, limit=10)
    lines = ["Top clans:"]
    for idx, clan in enumerate(clans, start=1):
        lines.append(f"{idx}. {clan.name} - score {clan.score}")
    await message.reply(italic("\n".join(lines)))


@router.message(Command("topclans"))
async def topclans_cmd(message: Message):
    await clans_cmd(message)


@router.message(Command("claninfo"))
async def claninfo_cmd(message: Message):
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        await message.reply(italic("Provide a clan name."))
        return
    name = parts[1].strip()
    async with async_session() as session:
        clan = await clan_by_name(session, name)
        if not clan:
            await message.reply(italic("Clan not found."))
            return
        members = await clan_member_count(session, clan)
        settings = await get_clan_settings(session, clan)
    await message.reply(
        italic(
            f"Clan: {clan.name}\nLeader: {clan.leader_id or 'None'}\nCo-leader: {clan.coleader_id or 'None'}\nMembers: {members}\nScore: {clan.score}\nMin join: {settings.min_join_points}"
        )
    )


async def _require_leader(session, user, clan: Clan | None):
    if not clan:
        return False
    if clan.leader_id == user.id:
        return True
    return False


@router.message(Command("setclanminpoints"))
async def set_min_points_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.reply(italic("Provide points number."))
        return
    min_points = int(parts[1])
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        membership = await get_membership(session, user)
        if not membership:
            await message.reply(italic("You are not in a clan."))
            return
        clan = await _load_clan(session, membership.clan_id)
        if not await _require_leader(session, user, clan):
            await message.reply(italic("Only the leader can do this."))
            return
        if not await set_leader_cooldown(session, clan):
            await message.reply(italic("Please wait before another change."))
            return
        await update_clan_min_points(session, clan, min_points)
        await session.commit()
    await message.reply(italic("Clan minimum points updated."))


@router.message(Command("setcoleader"))
async def set_coleader_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(italic("Reply to a user to use this command."))
        return
    target = message.reply_to_message.from_user
    if target.is_bot or target.id == message.from_user.id:
        await message.reply(italic("Invalid target."))
        return
    async with async_session() as session:
        leader = await get_or_create_user(session, message.from_user)
        target_user = await get_or_create_user(session, target)
        membership = await get_membership(session, leader)
        target_membership = await get_membership(session, target_user)
        if not membership or not target_membership or membership.clan_id != target_membership.clan_id:
            await message.reply(italic("Both users must be in the same clan."))
            return
        clan = await _load_clan(session, membership.clan_id)
        if not await _require_leader(session, leader, clan):
            await message.reply(italic("Only the leader can do this."))
            return
        if not await set_leader_cooldown(session, clan):
            await message.reply(italic("Please wait before another change."))
            return
        await set_coleader(session, clan, target_user)
        await session.commit()
    await message.reply(italic("Co-leader appointed."))


@router.message(Command("removecoleader"))
async def remove_coleader_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        leader = await get_or_create_user(session, message.from_user)
        membership = await get_membership(session, leader)
        if not membership:
            await message.reply(italic("You are not in a clan."))
            return
        clan = await _load_clan(session, membership.clan_id)
        if not await _require_leader(session, leader, clan):
            await message.reply(italic("Only the leader can do this."))
            return
        if not await set_leader_cooldown(session, clan):
            await message.reply(italic("Please wait before another change."))
            return
        await set_coleader(session, clan, None)
        await session.commit()
    await message.reply(italic("Co-leader removed."))


@router.message(Command("clean_topmembers"))
async def clean_topmembers_cmd(message: Message):
    if not ensure_group_message(message) or not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        leader = await get_or_create_user(session, message.from_user)
        membership = await get_membership(session, leader)
        if not membership:
            await message.reply(italic("You are not in a clan."))
            return
        clan = await _load_clan(session, membership.clan_id)
        if not await _require_leader(session, leader, clan):
            await message.reply(italic("Only the leader can do this."))
            return
        if not await set_leader_cooldown(session, clan):
            await message.reply(italic("Please wait before another change."))
            return
        await reset_weekly_points(session, clan)
        await session.commit()
    await message.reply(italic("Weekly clan stats reset."))
