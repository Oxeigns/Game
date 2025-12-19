from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from db import async_session
from repositories import get_or_create_group, get_or_create_user, log_message
from utils import ensure_group_message, italic

router = Router()


@router.message(Command("start"))
async def start_cmd(message: Message):
    if not message.from_user:
        return
    async with async_session() as session:
        await get_or_create_user(session, message.from_user)
        if ensure_group_message(message):
            await get_or_create_group(session, message.chat)
        await session.commit()
    await message.reply(italic("Hello! I'm ready to manage clans, points, and gifts."))


@router.message(Command("help"))
async def help_cmd(message: Message):
    text = (
        "BASIC: /start /help /ping\n"
        "SOCIAL: /hug /kiss /punch /bite /dare\n"
        "STATS: /points /top /stats\n"
        "RELATIONSHIPS: /lover /unlover /son /unson\n"
        "CLANS: /createclan NAME /joinclan NAME /leaveclan /clan /topclans /clans /claninfo NAME\n"
        "CLAN ADMIN: /setclanminpoints N /setcoleader (reply) /removecoleader /clean_topmembers\n"
        "GIFTS: /gifts /gift <gift_key> (reply) /gifthistory\n"
        "LEADERBOARDS: /leaderboard_on /leaderboard_off /leaderboard_now"
    )
    await message.reply(italic(text))


@router.message(Command("ping"))
async def ping_cmd(message: Message):
    await message.reply(italic("Pong."))


@router.message(F.chat.type.in_({"group", "supergroup"}), F.text)
async def track_activity(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        group = await get_or_create_group(session, message.chat)
        await log_message(session, user, group)
        await session.commit()
