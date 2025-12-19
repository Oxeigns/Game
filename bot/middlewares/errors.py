from __future__ import annotations

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message

from bot.utils.cards import render_card
from bot.utils.errors import BotError


class ErrorMiddleware(BaseMiddleware):
    """Catch user-facing errors and present consistent replies."""

    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except BotError as exc:
            await self._respond(event, exc.message)
        except TelegramAPIError:
            await self._respond(event, "I could not complete that action. Please ensure I have the required rights.")

    async def _respond(self, event, text: str):
        if isinstance(event, CallbackQuery):
            if event.message:
                await event.message.answer(render_card("⚠️ Oops", [text]))
            await event.answer(text, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(render_card("⚠️ Oops", [text]))
