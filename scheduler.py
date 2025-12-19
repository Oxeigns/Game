from __future__ import annotations

import asyncio
from datetime import datetime

from aiogram import Bot

from db import async_session
from handlers.leaderboards import build_leaderboard_text
from repositories import enabled_groups
from utils import italic

INTERVAL_SECONDS = 6 * 60 * 60


async def post_leaderboards(bot: Bot):
    async with async_session() as session:
        groups = await enabled_groups(session)
    for group in groups:
        try:
            text = await build_leaderboard_text(group.telegram_id)
            await bot.send_message(group.telegram_id, italic(text))
        except Exception:
            continue


async def leaderboard_scheduler(bot: Bot):
    while True:
        await post_leaderboards(bot)
        await asyncio.sleep(INTERVAL_SECONDS)
