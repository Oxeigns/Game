import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config import get_settings
from db import init_db
from handlers import basic, clans, gifts, leaderboards, relationships, social, stats
from scheduler import leaderboard_scheduler


async def main():
    settings = get_settings()
    bot = Bot(settings.token, parse_mode=ParseMode.HTML)
    bot["start_time"] = datetime.utcnow()
    await init_db()
    dp = Dispatcher()
    dp.include_router(social.router)
    dp.include_router(stats.router)
    dp.include_router(relationships.router)
    dp.include_router(clans.router)
    dp.include_router(leaderboards.router)
    dp.include_router(gifts.router)
    dp.include_router(basic.router)
    asyncio.create_task(leaderboard_scheduler(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
