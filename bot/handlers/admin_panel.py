from __future__ import annotations

from aiogram import Router, types
from aiogram.filters import Command

from bot.services import moderation_service
from bot.utils.cards import render_card

router = Router()


@router.message(Command("panel"))
async def cmd_panel(message: types.Message, session):
    settings = await moderation_service.get_group_settings(session, message.chat)
    lines = [
        f"🛡 Moderation: {'ON' if settings.get('max_warns') else 'OFF'}",
        f"🚫 Flood: {settings['flood_limit']}/{settings['flood_window']}s",
        f"👋 Welcome: {'ON' if settings['welcome_enabled'] else 'OFF'}",
        f"👋 Goodbye: {'ON' if settings['goodbye_enabled'] else 'OFF'}",
    ]
    await message.reply(render_card("🛠 Admin Panel", lines, footer="Use commands to configure"))
