from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message

from bot.config import settings
from bot.utils.errors import BotError, PermissionError


async def ensure_group_chat(message: Message) -> None:
    if not message.chat or message.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        raise BotError("This command only works in groups.")


async def ensure_private_chat(message: Message) -> None:
    if not message.chat or message.chat.type != ChatType.PRIVATE:
        raise BotError("This command is only available in a private chat with me.")


async def ensure_admin(message: Message) -> None:
    if not message.from_user:
        raise PermissionError("Unable to verify your permissions.")
    if message.from_user.id in settings.admin_ids:
        return
    await ensure_group_chat(message)
    try:
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    except TelegramForbiddenError:
        raise PermissionError("I need permission to view admin list.")
    except TelegramBadRequest:
        raise PermissionError("Could not verify admin status.")
    if member.status not in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}:
        raise PermissionError("Only group admins can use this command.")


async def ensure_target_actionable(bot: Bot, chat_id: int, target_id: int) -> None:
    try:
        status = await bot.get_chat_member(chat_id, target_id)
    except TelegramForbiddenError:
        raise BotError("I need permission to view member details before moderating.")
    except TelegramBadRequest:
        raise BotError("I could not find that user in this chat.")
    if status.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}:
        raise BotError("I cannot perform that action on admins or the chat owner.")
