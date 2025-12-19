"""Antiflood middleware using AntifloodService."""
from __future__ import annotations

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.config import settings
from bot.services.antiflood_service import AntifloodService, FloodSettings
from bot.services import moderation_service


class AntifloodMiddleware(BaseMiddleware):
    def __init__(self, service: AntifloodService):
        super().__init__()
        self.service = service

    async def __call__(self, handler, event: Message, data: dict):
        if event.chat.type not in ("group", "supergroup"):
            return await handler(event, data)
        session = data.get("session")
        if not session:
            return await handler(event, data)
        group_settings = await moderation_service.get_group_settings(session, event.chat)
        if not group_settings.get("antiflood_enabled", True):
            return await handler(event, data)
        flood_settings = FloodSettings(limit=group_settings["flood_limit"], window=group_settings["flood_window"])
        count = await self.service.hit(event.chat.id, event.from_user.id, flood_settings)
        if count > flood_settings.limit:
            try:
                await event.bot.delete_message(event.chat.id, event.message_id)
            except Exception:
                pass
            return  # silently drop
        return await handler(event, data)
