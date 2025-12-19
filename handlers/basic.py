from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from db import async_session, check_database
from repositories import get_or_create_group, get_or_create_user, increment_message_count
from utils import ensure_group_message, human_latency, italic

router = Router()


@router.message(Command("start"))
async def start_cmd(message: Message):
    if message.from_user is None or message.from_user.is_bot:
        return
    text = "Welcome! I'm a social stats bot. Use /help to see commands."
    await message.reply(italic(text))


@router.message(Command("help"))
async def help_cmd(message: Message):
    if message.from_user is None or message.from_user.is_bot:
        return
    text = (
        "Commands:\n"
        "Basic: /start /help /ping\n"
        "Social (reply): /hug /kiss /punch /bite /dare\n"
        "Stats: /points /top /stats\n"
        "Relationships: /lover /unlover /son /unson\n"
        "Clans: /createclan /joinclan /leaveclan /clan /topclans\n"
        "Leaderboards: /leaderboard_on /leaderboard_off /leaderboard_now /topgroups"
    )
    await message.reply(italic(text))


@router.message(Command("ping"))
async def ping_cmd(message: Message):
    if message.from_user is None or message.from_user.is_bot:
        return
    start = datetime.utcnow()
    db_status = "ok" if await check_database() else "down"
    latency = human_latency(start)
    uptime = "unknown"
    if message.bot and message.bot.get("start_time"):
        uptime_delta = datetime.utcnow() - message.bot["start_time"]
        uptime = str(uptime_delta).split(".")[0]
    info = f"Pong! Latency: {latency} ms | DB: {db_status} | Uptime: {uptime}"
    await message.reply(italic(info))


@router.message()
async def count_messages(message: Message):
    if not ensure_group_message(message):
        return
    if not message.from_user or message.from_user.is_bot:
        return
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user)
        group = await get_or_create_group(session, message.chat)
        group.title = message.chat.title or group.title
        await increment_message_count(session, user, group)
        await session.commit()
