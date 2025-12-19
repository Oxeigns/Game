from __future__ import annotations

import asyncio
import logging
from typing import Callable

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

from bot.config import settings
from bot.db.session import SessionLocal, engine, Base
from bot.handlers import start, admin_panel, moderation, economy, combat, fun, games
from bot.middlewares.antiflood import AntifloodMiddleware
from bot.middlewares.errors import ErrorMiddleware
from bot.services.antiflood_service import AntifloodService
from bot.utils.rate_limit import RateLimiter


async def setup_logging():
    level = getattr(logging, settings.logging.level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")
    # Toggle JSON renderer based on config to avoid pydantic field shadowing warning.
    processors = [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if settings.logging.json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )


async def init_db() -> None:
    # Ensure tables exist before polling to avoid runtime errors on new deployments.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def command_setup(bot: Bot):
    private_commands = [
        BotCommand(command="start", description="Open the main menu"),
        BotCommand(command="help", description="Command reference"),
        BotCommand(command="panel", description="Admin panel (DM-only)"),
        BotCommand(command="daily", description="Claim daily reward"),
        BotCommand(command="bal", description="Check balance"),
        BotCommand(command="transactions", description="Recent transactions"),
        BotCommand(command="toprich", description="Top balance"),
        BotCommand(command="truth", description="Truth prompt"),
        BotCommand(command="dare", description="Dare prompt"),
        BotCommand(command="puzzle", description="Puzzle"),
        BotCommand(command="brain", description="Riddle"),
        BotCommand(command="couples", description="Couples game"),
    ]
    group_commands = [
        BotCommand(command="daily", description="Claim daily reward"),
        BotCommand(command="bal", description="Check balance"),
        BotCommand(command="give", description="Transfer coins"),
        BotCommand(command="transactions", description="Recent transactions"),
        BotCommand(command="toprich", description="Top balance"),
        BotCommand(command="rob", description="Rob a member (reply)"),
        BotCommand(command="kill", description="Record a kill (reply)"),
        BotCommand(command="revive", description="Revive yourself"),
        BotCommand(command="protect", description="Shield yourself"),
        BotCommand(command="topkill", description="Top killers"),
        BotCommand(command="warn", description="Warn a user"),
        BotCommand(command="warns", description="View warns"),
        BotCommand(command="resetwarns", description="Reset warns"),
        BotCommand(command="mute", description="Mute user"),
        BotCommand(command="unmute", description="Unmute user"),
        BotCommand(command="ban", description="Ban user"),
        BotCommand(command="unban", description="Unban user"),
        BotCommand(command="kick", description="Kick user"),
        BotCommand(command="purge", description="Purge messages"),
        BotCommand(command="del", description="Delete a message"),
        BotCommand(command="rules", description="Show group rules"),
    ]
    await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())


async def main():
    await setup_logging()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()

    rate_limiter = RateLimiter(settings.resolved_redis_url)
    antiflood_service = AntifloodService(settings.resolved_redis_url)

    dp.update.middleware(ErrorMiddleware())

    # Middleware to inject DB session and rate limiter
    @dp.update.middleware()
    async def db_session_middleware(handler: Callable, event, data: dict):
        async with SessionLocal() as session:
            data["session"] = session
            data["rate_limiter"] = rate_limiter
            return await handler(event, data)
    dp.message.middleware(AntifloodMiddleware(antiflood_service))

    dp.include_routers(
        start.router,
        admin_panel.router,
        moderation.router,
        economy.router,
        combat.router,
        fun.router,
        games.router,
    )

    await command_setup(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
